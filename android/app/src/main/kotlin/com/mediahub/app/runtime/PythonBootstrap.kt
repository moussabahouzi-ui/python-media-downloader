package com.mediahub.app.runtime

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream

/**
 * Prepares the embedded CPython runtime for execution on Android.
 *
 * Android packages native code as `.so` files in `lib/<abi>/` (read-only,
 * loaded via `dlopen`) and Python source as compressed assets. This class
 * bridges the gap:
 *
 * 1. **Executable preparation**: copies `libpython3.11.so` from the
 *    read-only `nativeLibraryDir` to `filesDir/bin/python3` and marks it
 *    executable. Android's SELinux policy allows `exec` from `app_data_file`
 *    (the `filesDir` type). On Android 14+, the W^X (write XOR execute)
 *    policy is satisfied because we close the file before `setExecutable`.
 *
 * 2. **Stdlib extraction**: extracts `python_stdlib.zip` from assets to
 *    `filesDir/python/lib/python3.11/`. This includes pure-Python `.py`
 *    files and C extension `.so` files in `lib-dynload/`.
 *
 * 3. **Site-packages extraction**: extracts `python_packages.zip` from
 *    assets to `filesDir/python/lib/python3.11/site-packages/`. This
 *    includes yt-dlp, gallery-dl, instaloader, pydantic, and
 *    mediahub_engine.
 *
 * 4. **FFmpeg preparation**: copies `libffmpeg.so` to `filesDir/bin/ffmpeg`
 *    and marks it executable.
 *
 * 5. **Version tracking**: writes a marker file so subsequent launches skip
 *    extraction (saves ~1.5 s on cold start).
 *
 * All operations are idempotent — if the marker matches, nothing is done.
 * If extraction fails midway, the marker is not written, so the next launch
 * retries.
 */
object PythonBootstrap {

    private const val TAG = "PythonBootstrap"

    /** Asset names (must match the build script output). */
    private const val ASSET_STDLIB = "python_stdlib.zip"
    private const val ASSET_PACKAGES = "python_packages.zip"

    /**
     * Prepares the Python runtime for execution. Idempotent — if the
     * current extraction version matches, returns immediately.
     *
     * @return `true` if the runtime is ready to launch.
     */
    fun prepare(context: Context): Boolean {
        if (PythonPaths.isExtracted(context)) {
            Log.i(TAG, "Python runtime already extracted (v${PythonPaths.EXTRACTION_VERSION})")
            return verifyExecutables(context)
        }

        Log.i(TAG, "Preparing Python runtime (v${PythonPaths.EXTRACTION_VERSION})...")
        val started = System.currentTimeMillis()

        try {
            // Step 1: Prepare the python3 executable
            if (!prepareExecutable(context, "python3", PythonPaths.libpythonSo(context), PythonPaths.pythonExecutable(context))) {
                Log.e(TAG, "Failed to prepare python3 executable")
                return false
            }

            // Step 2: Prepare the ffmpeg executable (if present)
            val ffmpegSo = PythonPaths.libffmpegSo(context)
            if (ffmpegSo.exists()) {
                prepareExecutable(context, "ffmpeg", ffmpegSo, PythonPaths.ffmpegExecutable(context))
            } else {
                Log.w(TAG, "libffmpeg.so not found — FFmpeg features will be unavailable")
            }

            // Step 3: Extract the Python stdlib
            if (!extractAsset(context, ASSET_STDLIB, PythonPaths.pythonLib(context))) {
                Log.e(TAG, "Failed to extract Python stdlib")
                return false
            }

            // Step 4: Extract third-party packages (site-packages)
            // The zip contains the packages at the top level; extract into site-packages/
            val sitePackages = PythonPaths.sitePackages(context)
            sitePackages.mkdirs()
            if (!extractAsset(context, ASSET_PACKAGES, sitePackages)) {
                Log.e(TAG, "Failed to extract Python packages")
                return false
            }

            // Step 5: Write the version marker
            PythonPaths.markExtracted(context)

            val elapsed = System.currentTimeMillis() - started
            Log.i(TAG, "Python runtime prepared in ${elapsed}ms")
            return verifyExecutables(context)

        } catch (e: Exception) {
            Log.e(TAG, "Bootstrap failed", e)
            // Clean up partial extraction so the next launch retries cleanly
            PythonPaths.versionMarker(context).delete()
            return false
        }
    }

    /**
     * Copies a `.so` file from `nativeLibraryDir` to `filesDir/bin/<name>`
     * and marks it executable.
     *
     * Android packages native binaries as `lib<name>.so` in `lib/<abi>/`.
     * These are shared libraries designed for `dlopen`, not for `exec`.
     * However, a CPython interpreter compiled as a PIE executable and
     * renamed to `.so` for packaging can be `exec`'ed after being copied
     * to a writable location with the execute bit set.
     *
     * W^X (Write XOR Execute) on Android 14+: we write the file, close all
     * handles, then call `setExecutable`. The file is never open for writing
     * while it has the execute bit, satisfying the kernel policy.
     */
    private fun prepareExecutable(
        context: Context,
        name: String,
        sourceSo: File,
        targetExec: File,
    ): Boolean {
        if (!sourceSo.exists()) {
            Log.e(TAG, "Source .so not found: ${sourceSo.absolutePath}")
            return false
        }

        // Ensure the bin directory exists
        targetExec.parentFile?.mkdirs()

        // Copy the .so to the target path
        // Use a temporary name first, then rename — atomic on the same filesystem
        val tempFile = File(targetExec.parentFile, "$name.tmp")
        try {
            sourceSo.inputStream().use { input ->
                FileOutputStream(tempFile).use { output ->
                    input.copyTo(output)
                }
            }

            // Close all handles before setting executable (W^X compliance)
            if (!tempFile.renameTo(targetExec)) {
                // Rename failed — try copy + delete
                tempFile.copyTo(targetExec, overwrite = true)
                tempFile.delete()
            }

            // Set permissions: rwxr-xr-x (owner can exec, others can read/exec)
            targetExec.setReadable(true, false)
            targetExec.setWritable(true, true)
            targetExec.setExecutable(true, false)

            Log.i(TAG, "Prepared executable: ${targetExec.absolutePath} (${targetExec.length()} bytes)")
            return targetExec.canExecute()

        } catch (e: Exception) {
            Log.e(TAG, "Failed to prepare $name executable", e)
            tempFile.delete()
            return false
        }
    }

    /**
     * Extracts a zip asset to a target directory, preserving the internal
     * directory structure.
     *
     * Uses streaming extraction (ZipInputStream) to handle large zips
     * without loading them entirely into memory.
     */
    private fun extractAsset(context: Context, assetName: String, targetDir: File): Boolean {
        val asset = try {
            context.assets.open(assetName)
        } catch (e: Exception) {
            Log.e(TAG, "Asset not found: $assetName", e)
            return false
        }

        targetDir.mkdirs()
        var entryCount = 0

        ZipInputStream(asset).use { zis ->
            var entry: ZipEntry? = zis.nextEntry
            while (entry != null) {
                val outFile = File(targetDir, entry.name)

                // Security: prevent zip path traversal (../../etc/passwd)
                val targetBase = targetDir.canonicalPath
                val outPath = outFile.canonicalPath
                if (!outPath.startsWith(targetBase)) {
                    Log.w(TAG, "Skipping path traversal entry: ${entry.name}")
                    zis.closeEntry()
                    entry = zis.nextEntry
                    continue
                }

                if (entry.isDirectory) {
                    outFile.mkdirs()
                } else {
                    outFile.parentFile?.mkdirs()
                    FileOutputStream(outFile).use { fos ->
                        zis.copyTo(fos)
                    }
                    // Preserve the executable bit for .so files in lib-dynload
                    if (entry.name.endsWith(".so")) {
                        outFile.setExecutable(true, false)
                    }
                }

                entryCount++
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }

        Log.i(TAG, "Extracted $assetName: $entryCount entries → ${targetDir.absolutePath}")
        return true
    }

    /**
     * Verifies that the python3 executable exists and is executable.
     * Called after [prepare] to confirm the runtime is launchable.
     */
    fun verifyExecutables(context: Context): Boolean {
        val python = PythonPaths.pythonExecutable(context)
        if (!python.exists()) {
            Log.e(TAG, "python3 executable not found: ${python.absolutePath}")
            return false
        }
        if (!python.canExecute()) {
            Log.e(TAG, "python3 not executable: ${python.absolutePath}")
            return false
        }

        // Verify the stdlib has the critical _ssl module (common failure point)
        val sslSo = File(PythonPaths.libDynload(context), "_ssl.cpython-${PythonPaths.PYTHON_VERSION.replace(".", "")}-aarch64-linux-android.so")
        if (!sslSo.exists()) {
            // Try the generic name (some builds don't include the platform tag)
            val altSsl = File(PythonPaths.libDynload(context), "_ssl.so")
            if (!altSsl.exists()) {
                Log.w(TAG, "_ssl.so not found — HTTPS will not work")
            }
        }

        return true
    }

    /**
     * Forces a re-extraction on the next [prepare] call, regardless of the
     * version marker. Useful after an app update that bundles new packages.
     */
    fun forceReextract(context: Context) {
        PythonPaths.versionMarker(context).delete()
        Log.i(TAG, "Forced re-extraction on next launch")
    }
}
