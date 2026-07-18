package com.mediahub.app.runtime

import android.content.Context
import java.io.File

/**
 * Resolves all filesystem paths required to run an embedded CPython
 * interpreter on Android.
 *
 * Android packaging constraints mean native libraries (`.so` files) land in
 * [Context.nativeLibraryDir] (read-only, loaded via `dlopen`), while Python
 * source code and C extension modules must be shipped as compressed assets
 * and extracted at first run to [Context.filesDir] (read-write).
 *
 * This object centralizes every path the runtime needs so that
 * [PythonBootstrap] and [PythonRuntime] stay in sync.
 *
 * Directory layout after first-run extraction:
 * ```
 * filesDir/
 *   bin/
 *     python3          ← executable copy of libpython3.11.so
 *     ffmpeg            ← executable copy of libffmpeg.so
 *   python/            ← PYTHONHOME
 *     lib/
 *       python3.11/    ← PYTHONPATH entry 1 (stdlib)
 *         *.py
 *         lib-dynload/  ← C extension .so files (_ssl, _hashlib, sqlite3, …)
 *         site-packages/← PYTHONPATH entry 2 (yt-dlp, gallery-dl, …)
 *           yt_dlp/
 *           gallery_dl/
 *           instaloader/
 *           pydantic/
 *           mediahub_engine/
 *   engine/            ← work directory (SQLite DB, partial files, recycle bin)
 *   .python_version    ← marker file; if present and matches, skip extraction
 * ```
 */
object PythonPaths {

    /** The CPython version this build targets. Must match the build script. */
    const val PYTHON_VERSION = "3.11"
    const val PYTHON_VERSION_FULL = "3.11.9"

    /** The extraction version. Bump when the bundled assets change. */
    const val EXTRACTION_VERSION = "1"

    // ---- directory paths ----

    /** `filesDir/bin` — holds the executable copies of python3 and ffmpeg. */
    fun binDir(context: Context): File =
        File(context.filesDir, "bin").also { it.mkdirs() }

    /** `filesDir/python` — PYTHONHOME root. */
    fun pythonHome(context: Context): File =
        File(context.filesDir, "python")

    /** `filesDir/python/lib/python3.11` — stdlib root (PYTHONPATH entry 1). */
    fun pythonLib(context: Context): File =
        File(pythonHome(context), "lib/python$PYTHON_VERSION")

    /** `filesDir/python/lib/python3.11/lib-dynload` — C extension .so files. */
    fun libDynload(context: Context): File =
        File(pythonLib(context), "lib-dynload")

    /** `filesDir/python/lib/python3.11/site-packages` — third-party packages. */
    fun sitePackages(context: Context): File =
        File(pythonLib(context), "site-packages")

    /** `filesDir/engine` — engine work directory (SQLite, partials, recycle). */
    fun workDir(context: Context): File =
        File(context.filesDir, "engine").also { it.mkdirs() }

    // ---- executable paths ----

    /** `filesDir/bin/python3` — the executable interpreter. */
    fun pythonExecutable(context: Context): File =
        File(binDir(context), "python3")

    /** `filesDir/bin/ffmpeg` — the executable FFmpeg binary. */
    fun ffmpegExecutable(context: Context): File =
        File(binDir(context), "ffmpeg")

    // ---- native library paths (read-only, from APK) ----

    /** The APK's native library directory, e.g. `/data/app/.../lib/arm64/`. */
    fun nativeLibraryDir(context: Context): String =
        context.applicationInfo.nativeLibraryDir

    /** `libpython3.11.so` in the native library directory. */
    fun libpythonSo(context: Context): File =
        File(nativeLibraryDir(context), "libpython$PYTHON_VERSION.so")

    /** `libffmpeg.so` in the native library directory. */
    fun libffmpegSo(context: Context): File =
        File(nativeLibraryDir(context), "libffmpeg.so")

    // ---- environment variable values ----

    /** The PYTHONHOME value: `filesDir/python`. */
    fun pythonHomePath(context: Context): String =
        pythonHome(context).absolutePath

    /**
     * The PYTHONPATH value: stdlib + lib-dynload + site-packages.
     * The lib-dynload directory is included explicitly so `dlopen`-loaded
     * C extensions resolve correctly.
     */
    fun pythonPath(context: Context): String =
        listOf(
            pythonLib(context).absolutePath,
            libDynload(context).absolutePath,
            sitePackages(context).absolutePath,
        ).joinToString(":")

    /**
     * The LD_LIBRARY_PATH value: the native library directory.
     * This is critical — without it, CPython cannot `dlopen` its own C
     * extension modules (`_ssl.so`, `_hashlib.so`, `sqlite3.so`, etc.)
     * because they link against `libpython3.11.so`, `libssl.so`, etc.
     * which live in `nativeLibraryDir`.
     */
    fun ldLibraryPath(context: Context): String =
        nativeLibraryDir(context)

    // ---- marker / version ----

    /** `filesDir/.python_version` — if it contains [EXTRACTION_VERSION],
     *  extraction is skipped on subsequent launches. */
    fun versionMarker(context: Context): File =
        File(context.filesDir, ".python_version")

    /** Returns `true` if the currently extracted runtime matches [EXTRACTION_VERSION]. */
    fun isExtracted(context: Context): Boolean {
        val marker = versionMarker(context)
        return marker.exists() && marker.readText().trim() == EXTRACTION_VERSION
    }

    /** Writes the version marker after a successful extraction. */
    fun markExtracted(context: Context) {
        versionMarker(context).writeText(EXTRACTION_VERSION)
    }
}
