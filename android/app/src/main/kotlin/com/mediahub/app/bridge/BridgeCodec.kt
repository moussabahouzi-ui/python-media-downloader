package com.mediahub.app.bridge

/**
 * Typed representation of a bridge envelope error returned to Flutter.
 *
 * Carries a stable [code] (see [MethodChannelContract.Errors]), a
 * user-presentable [message], and optional structured [details]. Mapped to the
 * wire format by [EngineMethodChannel].
 */
data class BridgeError(
    val code: String,
    val message: String,
    val details: Map<String, Any?> = emptyMap(),
) {
    fun toMap(): Map<String, Any?> = mapOf(
        MethodChannelContract.FIELD_ERROR_CODE to code,
        MethodChannelContract.FIELD_ERROR_MESSAGE to message,
        MethodChannelContract.FIELD_ERROR_DETAILS to details,
    )
}

/** A typed success envelope returned to Flutter. */
data class BridgeSuccess(
    val callId: String,
    val data: Map<String, Any?>,
)

/**
 * Result of parsing an incoming method-channel call. Encodes the validation
 * step that runs before any handler is dispatched.
 */
sealed class ParsedCall {
    data class Valid(
        val callId: String,
        val method: String,
        val params: Map<String, Any?>,
    ) : ParsedCall()

    data class Invalid(val error: BridgeError) : ParsedCall()
}

/**
 * Pure, side-effect-free parser for the bridge envelope. Kept separate from
 * the channel so it is unit-testable without a Flutter engine.
 */
object BridgeEnvelopeParser {

    fun parse(raw: Any?): ParsedCall {
        if (raw !is Map<*, *>) {
            return ParsedCall.Invalid(
                BridgeError(
                    MethodChannelContract.Errors.INVALID_PARAMS,
                    "Expected a map argument",
                ),
            )
        }

        val bridgeVersion = (raw[MethodChannelContract.FIELD_BRIDGE_VERSION] as? Number)?.toInt()
        if (bridgeVersion == null || bridgeVersion != MethodChannelContract.BRIDGE_VERSION) {
            return ParsedCall.Invalid(
                BridgeError(
                    MethodChannelContract.Errors.BRIDGE_VERSION_MISMATCH,
                    "Bridge version mismatch",
                    mapOf(
                        "expected" to MethodChannelContract.BRIDGE_VERSION,
                        "actual" to bridgeVersion,
                    ),
                ),
            )
        }

        val callId = raw[MethodChannelContract.FIELD_CALL_ID] as? String
        val method = raw[MethodChannelContract.FIELD_METHOD] as? String
        if (callId.isNullOrBlank() || method.isNullOrBlank()) {
            return ParsedCall.Invalid(
                BridgeError(
                    MethodChannelContract.Errors.INVALID_PARAMS,
                    "Missing callId or method",
                ),
            )
        }

        @Suppress("UNCHECKED_CAST")
        val params = (raw[MethodChannelContract.FIELD_PARAMS] as? Map<String, Any?>)
            ?.mapValues { it.value }
            ?: emptyMap()

        return ParsedCall.Valid(callId, method, params)
    }

    fun successEnvelope(success: BridgeSuccess): Map<String, Any?> = mapOf(
        MethodChannelContract.FIELD_BRIDGE_VERSION to MethodChannelContract.BRIDGE_VERSION,
        MethodChannelContract.FIELD_CALL_ID to success.callId,
        MethodChannelContract.FIELD_OK to true,
        MethodChannelContract.FIELD_DATA to success.data,
    )

    fun errorEnvelope(callId: String, error: BridgeError): Map<String, Any?> = mapOf(
        MethodChannelContract.FIELD_BRIDGE_VERSION to MethodChannelContract.BRIDGE_VERSION,
        MethodChannelContract.FIELD_CALL_ID to callId,
        MethodChannelContract.FIELD_OK to false,
        MethodChannelContract.FIELD_ERROR to error.toMap(),
    )

    fun eventEnvelope(name: String, data: Map<String, Any?>): Map<String, Any?> = mapOf(
        MethodChannelContract.FIELD_BRIDGE_VERSION to MethodChannelContract.BRIDGE_VERSION,
        "event" to name,
        MethodChannelContract.FIELD_DATA to data,
    )
}
