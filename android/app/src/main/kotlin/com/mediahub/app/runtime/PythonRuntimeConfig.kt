package com.mediahub.app.runtime

import android.content.Context
import java.io.File

/**
 * Configuration for the embedded CPython runtime on Android.
 *
 * Built from a [Context] via [forApp]. All paths are resolved by
 * [PythonPaths], which centralizes the directory layout.
 *
 * The runtime is launched as a child process via [ProcessBuilder] using the
 * executable at [PythonPaths.pythonExecutable]. The process environment is
 * configured with:
 * - `PYTHONHOME` → the extracted stdlib root
 * - `PYTHONPATH` → stdlib + lib-dynload + site-packages
 * - `LD_LIBRARY_PATH` → the APK's `nativeLibraryDir` (so CPython can `dlopen`
 *   its C extension modules: `_ssl.so`, `_hashlib.so`, `sqlite3.so`, etc.)
 * - `PYTHONUNBUFFERED=1` → critical for line-delimited JSON-RPC framing
 * - `PYTHONIOENCODING=utf-8` → deterministic encoding
 * - `MEDIAHUB_WORKDIR` → the engine's work directory
 *
 * @see PythonPaths for the complete directory layout.
 * @see PythonBootstrap for first-run extraction.
 */
data class PythonRuntimeConfig(
    /** Absolute path to the `python3` executable (in `filesDir/bin/`). */
    val executable: String,
    /** The Python module to run: `mediahub_engine`. */
    val engineModule: String,
    /** Engine work directory (SQLite DB, partial files, recycle bin). */
    val workDir: File,
    /** `PYTHONHOME` value. */
    val pythonHome: String,
    /** `PYTHONPATH` value (colon-separated). */
    val pythonPath: String,
    /** `LD_LIBRARY_PATH` value (the native library directory). */
    val ldLibraryPath: String,
    /** Timeout for the initial process health check (ms). */
    val startTimeoutMs: Long = 15_000L,
    /** Default per-call timeout (ms). */
    val callTimeoutMs: Long = 60_000L,
) {

    companion object {
        /**
         * Builds the config from the current application context.
         *
         * Must be called after [PythonBootstrap.prepare] has succeeded.
         */
        fun forApp(context: Context): PythonRuntimeConfig {
            return PythonRuntimeConfig(
                executable = PythonPaths.pythonExecutable(context).absolutePath,
                engineModule = "mediahub_engine",
                workDir = PythonPaths.workDir(context),
                pythonHome = PythonPaths.pythonHomePath(context),
                pythonPath = PythonPaths.pythonPath(context),
                ldLibraryPath = PythonPaths.ldLibraryPath(context),
            )
        }
    }
}
