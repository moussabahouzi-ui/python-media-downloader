package com.mediahub.app.runtime

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.io.BufferedReader
import java.io.BufferedWriter
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.io.Reader
import java.io.Writer
import java.util.concurrent.atomic.AtomicInteger

/**
 * Owns the lifecycle of the embedded CPython engine child process and the
 * line-delimited JSON-RPC conversation over its stdio.
 *
 * **Android-specific behavior:**
 *
 * The Python interpreter is packaged as `libpython3.11.so` in the APK's
 * `lib/<abi>/` directory. At first run, [PythonBootstrap] copies it to
 * `filesDir/bin/python3` and marks it executable. The process is then
 * launched via [ProcessBuilder] with the following environment:
 *
 * - `PYTHONHOME` → extracted stdlib root (`filesDir/python`)
 * - `PYTHONPATH` → stdlib + lib-dynload + site-packages
 * - `LD_LIBRARY_PATH` → `nativeLibraryDir` (so CPython can `dlopen` C
 *   extensions like `_ssl.so`, `_hashlib.so`, `sqlite3.so`)
 * - `PYTHONUNBUFFERED=1` → unbuffered stdio for line-delimited JSON-RPC
 * - `PYTHONIOENCODING=utf-8` → deterministic encoding
 * - `MEDIAHUB_WORKDIR` → engine work directory
 *
 * The process is launched with `-u` (unbuffered) and `-m mediahub_engine`.
 * stdout carries JSON-RPC responses/notifications; stderr carries structured
 * JSON logs (forwarded to logcat).
 *
 * Responsibilities:
 *  - call [PythonBootstrap.prepare] before first start (ensures the
 *    executable and stdlib are extracted)
 *  - spawn `python3 -u -m mediahub_engine` as a child process
 *  - write JSON-RPC requests to stdin (one object per line, compact)
 *  - read JSON-RPC responses / notifications from stdout (one per line)
 *  - capture stderr for diagnostics (structured logging)
 *  - expose a suspend [call] API with per-call timeouts and correlation
 *  - expose a [notifications] flow for unsolicited events (progress, etc.)
 *
 * The runtime is process-singleton by design: one engine per app process,
 * hosted by [com.mediahub.app.services.DownloadForegroundService].
 */
class PythonRuntime(
    private val context: Context,
    private val config: PythonRuntimeConfig,
) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()

    @Volatile private var process: Process? = null
    @Volatile private var stdin: Writer? = null
    @Volatile private var readerJob: Job? = null

    private val nextId = AtomicInteger(1)
    private val pending = mutableMapOf<Int, CompletableResponse>()
    private val _notifications = MutableSharedFlow<JSONObject>(
        extraBufferCapacity = 256,
    )

    /** Unsolicited engine notifications (no `id`). */
    val notifications: SharedFlow<JSONObject> = _notifications.asSharedFlow()

    @Volatile var isRunning: Boolean = false
        private set

    /**
     * Starts the engine. Ensures the Python runtime is extracted and
     * executable before launching the process. Idempotent; no-op if already
     * running.
     */
    suspend fun start(): Boolean = mutex.withLock {
        if (isRunning) return@withLock true
        return@withLock try {
            // Step 1: Ensure the Python executable and stdlib are extracted.
            if (!PythonBootstrap.prepare(context)) {
                Log.e(TAG, "Python bootstrap failed — cannot start runtime")
                return@withLock false
            }
            // Step 2: Launch the process.
            doStart()
        } catch (t: Throwable) {
            Log.e(TAG, "Failed to start Python runtime", t)
            false
        }
    }

    private suspend fun doStart(): Boolean {
        val executable = config.executable
        val executableFile = java.io.File(executable)

        // Verify the executable exists and is executable.
        if (!executableFile.exists()) {
            Log.e(TAG, "Python executable not found: $executable")
            return false
        }
        if (!executableFile.canExecute()) {
            Log.e(TAG, "Python executable not executable: $executable")
            // Attempt to fix permissions
            executableFile.setExecutable(true, false)
            if (!executableFile.canExecute()) {
                Log.e(TAG, "Cannot set executable permission on: $executable")
                return false
            }
        }

        Log.i(TAG, "Launching Python: $executable -u -m ${config.engineModule}")

        val pb = ProcessBuilder(
            executable,
            "-u",  // unbuffered stdio — critical for line-delimited JSON-RPC
            "-m",
            config.engineModule,
        ).apply {
            directory(config.workDir)
            redirectErrorStream(false)  // keep stdout/stderr separate

            // ---- Environment variables — CRITICAL for CPython on Android ----

            // PYTHONHOME: tells CPython where to find its stdlib.
            // Without this, Python cannot find Lib/ and fails immediately.
            environment()["PYTHONHOME"] = config.pythonHome

            // PYTHONPATH: tells CPython where to find importable modules.
            // Includes lib-dynload (C extensions) and site-packages (yt-dlp etc.).
            environment()["PYTHONPATH"] = config.pythonPath

            // LD_LIBRARY_PATH: tells the dynamic linker where to find shared
            // libraries. CPython's C extensions (_ssl.so, _hashlib.so,
            // sqlite3.so, etc.) link against libpython3.11.so, libssl.so,
            // libcrypto.so, libsqlite3.so — all in nativeLibraryDir.
            // Without this, dlopen() fails with "library not found".
            environment()["LD_LIBRARY_PATH"] = config.ldLibraryPath

            // Unbuffered I/O — critical for JSON-RPC line framing.
            // Without this, Python buffers stdout and Kotlin never receives
            // responses until the buffer fills (4 KB) or the process exits.
            environment()["PYTHONUNBUFFERED"] = "1"
            environment()["PYTHONIOENCODING"] = "utf-8"

            // Disable writing .pyc files — saves disk I/O and space.
            environment()["PYTHONDONTWRITEBYTECODE"] = "1"

            // Engine work directory — the engine reads this to find its
            // SQLite DB, partial files, and recycle bin.
            environment()["MEDIAHUB_WORKDIR"] = config.workDir.absolutePath

            // FFmpeg path — if the binary was extracted, add its directory
            // to PATH so yt-dlp and ffmpeg-python can find it.
            val ffmpeg = PythonPaths.ffmpegExecutable(context)
            if (ffmpeg.exists() && ffmpeg.canExecute()) {
                val currentPath = environment()["PATH"] ?: "/system/bin:/system/xbin"
                environment()["PATH"] = "${ffmpeg.parentFile?.absolutePath}:$currentPath"
                environment()["FFMPEG_BINARY"] = ffmpeg.absolutePath
            }

            // TLS/SSL: ensure the bundled CA certificates are used.
            // The build script bundles cacert.pem in the stdlib.
            // Python's ssl module finds it via PYTHONHOME automatically.
        }

        val proc = pb.start()
        process = proc
        stdin = BufferedWriter(OutputStreamWriter(proc.outputStream, Charsets.UTF_8))

        // Start reading stdout (JSON-RPC responses) and stderr (logs) immediately.
        readerJob = scope.launch {
            readLoop(BufferedReader(InputStreamReader(proc.inputStream, Charsets.UTF_8)))
        }
        scope.launch {
            drainStderr(BufferedReader(InputStreamReader(proc.errorStream, Charsets.UTF_8)))
        }

        // Wait briefly to confirm the process didn't exit immediately
        // (e.g. missing PYTHONHOME, bad PYTHONPATH, missing .so).
        val alive = withTimeoutOrNull(config.startTimeoutMs) {
            // Poll for liveness; if the binary is missing or PYTHONHOME is
            // wrong, the process exits within ~100 ms.
            delay(100)
            if (!proc.isAlive) return@withTimeoutOrNull false
            delay(200)  // give the engine time to boot and print its ready log
            proc.isAlive
        } ?: false

        isRunning = alive
        if (!alive) {
            val exitInfo = runCatching { proc.exitValue() }.getOrNull()
            Log.e(TAG, "Python runtime not alive (exit=$exitInfo, timeout=${exitInfo == null})")
            // Read any remaining stderr for diagnostics
            val errorOutput = proc.errorStream.bufferedReader().readText()
            if (errorOutput.isNotEmpty()) {
                Log.e(TAG, "Python stderr:\n$errorOutput")
            }
        } else {
            Log.i(TAG, "Python runtime started successfully (pid=${proc.pid()})")
        }
        alive
    }

    private suspend fun readLoop(reader: Reader) {
        val br = reader as? BufferedReader ?: BufferedReader(reader)
        try {
            while (scope.isActive) {
                val line = br.readLine() ?: break
                if (line.isBlank()) continue
                val json = try {
                    JSONObject(line)
                } catch (e: Exception) {
                    Log.w(TAG, "Non-JSON line from engine: $line")
                    continue
                }
                if (json.has("id")) {
                    val id = json.getInt("id")
                    val completable = synchronized(pending) { pending.remove(id) }
                    completable?.complete(json)
                } else {
                    // Notification — no id.
                    _notifications.tryEmit(json)
                }
            }
        } catch (e: Exception) {
            if (scope.isActive) Log.e(TAG, "Engine stdout reader crashed", e)
        } finally {
            isRunning = false
            // Complete any pending requests with null (they'll return null → timeout)
            synchronized(pending) {
                pending.values.forEach { it.completeNull() }
                pending.clear()
            }
        }
    }

    private fun drainStderr(reader: Reader) {
        val br = reader as? BufferedReader ?: BufferedReader(reader)
        try {
            while (true) {
                val line = br.readLine() ?: break
                // Structured engine logs land here; forward to logcat.
                Log.i(TAG, "[engine] $line")
            }
        } catch (_: Exception) {
            // Best-effort; ignored.
        }
    }

    /**
     * Sends a JSON-RPC request and awaits the matching response.
     * Returns `null` on timeout or if the engine is not running.
     */
    suspend fun call(method: String, params: Map<String, Any?> = emptyMap()): JSONObject? {
        if (!isRunning && !start()) return null
        val id = nextId.getAndIncrement()
        val completable = CompletableResponse()
        synchronized(pending) { pending[id] = completable }

        val request = JSONObject().apply {
            put("jsonrpc", "2.0")
            put("id", id)
            put("method", method)
            put("params", JSONObject(params))
        }

        try {
            writeLine(request.toString())
        } catch (e: Exception) {
            synchronized(pending) { pending.remove(id) }
            Log.e(TAG, "Failed to write request: $method", e)
            return null
        }

        val response = withTimeoutOrNull(config.callTimeoutMs) { completable.await() }
        if (response == null) {
            synchronized(pending) { pending.remove(id) }
            Log.w(TAG, "Engine call timed out: $method (timeout=${config.callTimeoutMs}ms)")
        }
        return response
    }

    private fun writeLine(line: String) {
        val writer = stdin ?: throw IllegalStateException("engine not started")
        // Synchronized to prevent interleaving from concurrent calls.
        synchronized(writer) {
            writer.write(line)
            writer.write("\n")
            writer.flush()
        }
    }

    /** Gracefully stops the engine. */
    suspend fun stop(): Boolean = mutex.withLock {
        if (!isRunning) return@withLock true
        // Ask the engine to shut down gracefully.
        runCatching { call("engine.shutdown") }
        // Give it 2 seconds to flush and exit.
        process?.apply {
            runCatching {
                outputStream.close()
                waitFor(2_000, java.util.concurrent.TimeUnit.MILLISECONDS)
            }
            if (isAlive) destroyForcibly()
        }
        readerJob?.cancel()
        process = null
        stdin = null
        isRunning = false
        Log.i(TAG, "Python runtime stopped")
        true
    }

    fun shutdownNow() {
        scope.launch { stop() }
    }

    fun dispose() {
        // Gracefully stop the Python process before cancelling the scope,
        // otherwise the stop() coroutine is cancelled before it can run.
        runBlocking { stop() }
        scope.cancel()
    }

    companion object {
        private const val TAG = "PythonRuntime"
    }
}

/** A single-shot completable for a JSON-RPC response, backed by a deferred. */
private class CompletableResponse {
    private val deferred = CompletableDeferred<JSONObject?>()

    fun complete(value: JSONObject) {
        deferred.complete(value)
    }

    fun completeNull() {
        deferred.complete(null)
    }

    suspend fun await(): JSONObject? = deferred.await()
}
