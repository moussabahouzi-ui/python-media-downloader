/// Low-level exception types thrown inside the data/platform layers.
///
/// These are *never* propagated to the presentation layer; the data layer
/// catches them and converts them into [Failure]s via [FailureMapper].
library;

import 'failures.dart';

/// Thrown when the method channel returns an error envelope.
class BridgeException implements Exception {
  const BridgeException({
    required this.code,
    required this.message,
    this.details,
  });

  final String code;
  final String message;
  final Map<String, Object?>? details;

  @override
  String toString() => 'BridgeException($code): $message';
}

/// Thrown when the platform returns a result that cannot be decoded.
class BridgeCodecException implements Exception {
  const BridgeCodecException(this.message);
  final String message;

  @override
  String toString() => 'BridgeCodecException: $message';
}

/// Maps a [BridgeException] (or raw platform error) to a [Failure].
class FailureMapper {
  const FailureMapper();

  Failure fromBridge(BridgeException e) {
    switch (e.code) {
      case 'BRIDGE_VERSION_MISMATCH':
        final expected = e.details?['expected'] as int?;
        final actual = e.details?['actual'] as int?;
        if (expected != null && actual != null) {
          return BridgeVersionMismatchFailure(expected: expected, actual: actual);
        }
        return const InternalFailure('Bridge version mismatch');
      case 'ENGINE_NOT_READY':
        return EngineNotReadyFailure(e.message);
      case 'ENGINE_TIMEOUT':
        return const EngineTimeoutFailure();
      case 'PROVIDER_NOT_FOUND':
        final url = e.details?['url'] as String? ?? '';
        return ProviderNotFoundFailure(url);
      case 'UNKNOWN_METHOD':
        return UnknownMethodFailure(e.details?['method'] as String? ?? '');
      case 'INVALID_PARAMS':
        return InvalidParamsFailure(e.message);
      case 'INTERNAL':
        return InternalFailure(e.message, details: e.details);
      default:
        return InternalFailure(e.message, details: {'code': e.code});
    }
  }

  Failure fromObject(Object error) {
    if (error is BridgeException) return fromBridge(error);
    return InternalFailure(error.toString());
  }
}
