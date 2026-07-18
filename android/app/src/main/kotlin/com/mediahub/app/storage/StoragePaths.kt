package com.mediahub.app.storage

import android.content.Context
import android.os.Build
import android.os.Environment
import java.io.File

/**
 * Resolves all on-device storage locations used by MediaHub.
 *
 * The app uses scoped storage only in the `standard` flavor. All downloads
 * land under a public `MediaHub/Downloads/` directory inside the appropriate
 * media-scoped folder, which the system indexes for the user's gallery/apps.
 */
object StoragePaths {

    /** App-internal working directory (engine scratch space, partial files). */
    fun workDir(context: Context): File =
        File(context.filesDir, "engine").apply { mkdirs() }

    /** App-internal partial-download directory. */
    fun partialDir(context: Context): File =
        File(workDir(context), "partial").apply { mkdirs() }

    /** Recycle bin (soft-delete) directory. */
    fun recycleBinDir(context: Context): File =
        File(workDir(context), "recycle").apply { mkdirs() }

    /** Public downloads root visible to other apps. */
    fun downloadsRoot(context: Context): File {
        // Prefer Movies/DCIM-style media folders per category at runtime; the
        // root anchor lives under the standard Downloads area.
        val base = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                ?: File(context.filesDir, "downloads")
        } else {
            File(Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS,
            ), "MediaHub")
        }
        return base.apply { mkdirs() }
    }

    /** Per-category destination directory. */
    fun categoryDir(context: Context, category: String): File =
        File(downloadsRoot(context), category).apply { mkdirs() }

    /** Resolves a safe output filename, avoiding collisions. */
    fun resolveUnique(dir: File, baseName: String, ext: String): File {
        val safeBase = baseName.ifBlank { "media" }
        var candidate = File(dir, "$safeBase.$ext")
        var i = 1
        while (candidate.exists()) {
            candidate = File(dir, "$safeBase ($i).$ext")
            i++
        }
        return candidate
    }
}
