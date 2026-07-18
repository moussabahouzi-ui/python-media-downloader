package com.mediahub.app.bridge

/**
 * The authoritative method-channel contract shared between Flutter (Dart) and
 * Android (Kotlin).
 *
 * This object mirrors `lib/core/platform/method_channels/engine_channel_types.dart`
 * and `docs/BRIDGE_CONTRACT.md`. Any change here is a breaking change unless
 * additive and MUST be accompanied by a `bridgeVersion` bump.
 */
object MethodChannelContract {

    /** Channel name shared with Dart. */
    const val CHANNEL = "com.mediahub.app/engine"

    /** Event channel for streaming notifications back to Flutter. */
    const val EVENTS_CHANNEL = "com.mediahub.app/engine/events"

    /** Current bridge envelope version. */
    const val BRIDGE_VERSION = 1

    /** The single method the Dart side invokes on the [CHANNEL]. */
    const val METHOD_INVOKE = "invoke"

    // ---- Envelope field names ----
    const val FIELD_BRIDGE_VERSION = "bridgeVersion"
    const val FIELD_CALL_ID = "callId"
    const val FIELD_METHOD = "method"
    const val FIELD_PARAMS = "params"
    const val FIELD_OK = "ok"
    const val FIELD_DATA = "data"
    const val FIELD_ERROR = "error"
    const val FIELD_ERROR_CODE = "code"
    const val FIELD_ERROR_MESSAGE = "message"
    const val FIELD_ERROR_DETAILS = "details"

    // ---- Method names (domain.action) ----
    object Methods {
        const val ENGINE_PING = "engine.ping"
        const val ENGINE_VERSION = "engine.version"
        const val ENGINE_SHUTDOWN = "engine.shutdown"
    }

    // ---- Event names ----
    object Events {
        const val ENGINE_READY = "engine.ready"
        const val ENGINE_STOPPED = "engine.stopped"
        const val DOWNLOAD_PROGRESS = "download.progress"
    }

    // ---- Error codes ----
    object Errors {
        const val BRIDGE_VERSION_MISMATCH = "BRIDGE_VERSION_MISMATCH"
        const val UNKNOWN_METHOD = "UNKNOWN_METHOD"
        const val INVALID_PARAMS = "INVALID_PARAMS"
        const val ENGINE_NOT_READY = "ENGINE_NOT_READY"
        const val ENGINE_TIMEOUT = "ENGINE_TIMEOUT"
        const val PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
        const val INTERNAL = "INTERNAL"
    }
}
