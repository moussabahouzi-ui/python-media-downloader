/// Failure taxonomy used across the domain and data layers.
///
/// A [Failure] describes *why* an operation failed in a transport-agnostic,
/// user-presentable way. It is the single error currency crossing layer
/// boundaries inside Flutter. Bridge-level errors from the method channel are
/// mapped to [Failure]s by the data layer before reaching the presentation
/// layer.
library;

import 'package:flutter/foundation.dart';

/// Base class for all failures.
@immutable
sealed class Failure {
  const Failure(this.message, {this.code, this.details});

  /// Stable machine-readable code (mirrors `docs/BRIDGE_CONTRACT.md`).
  final String? code;

  /// Human-readable message. Safe to surface in the UI.
  final String message;

  /// Optional structured details for diagnostics.
  final Map<String, Object?>? details;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Failure &&
          runtimeType == other.runtimeType &&
          code == other.code &&
          message == other.message;

  @override
  int get hashCode => Object.hash(runtimeType, code, message);

  @override
  String toString() => '$runtimeType(code: $code, message: $message)';
}

/// The bridge versions on the two sides do not match.
final class BridgeVersionMismatchFailure extends Failure {
  // 💎 تم إزالة const من هنا لأن الخريطة بالأسفل تحتوي على بيانات متغيرة
  BridgeVersionMismatchFailure({
    required int expected,
    required int actual,
  }) : super(
          'Bridge version mismatch',
          code: 'BRIDGE_VERSION_MISMATCH',
          details: {'expected': expected, 'actual': actual},
        );
}

/// The Python engine is not running or crashed.
final class EngineNotReadyFailure extends Failure {
  const EngineNotReadyFailure([String? reason])
      : super(
          reason ?? 'Media engine is not running',
          code: 'ENGINE_NOT_READY',
        );
}

/// A call to the engine timed out.
final class EngineTimeoutFailure extends Failure {
  const EngineTimeoutFailure()
      : super('Engine did not respond in time', code: 'ENGINE_TIMEOUT');
}

/// No provider matched the supplied URL.
final class ProviderNotFoundFailure extends Failure {
  // 💎 تم إزالة const من هنا
  ProviderNotFoundFailure(String url)
      : super(
          'No provider supports this URL',
          code: 'PROVIDER_NOT_FOUND',
          details: {'url': url},
        );
}

/// The requested method does not exist on the bridge.
final class UnknownMethodFailure extends Failure {
  // 💎 تم إزالة const من هنا
  UnknownMethodFailure(String method)
      : super(
          'Unknown bridge method',
          code: 'UNKNOWN_METHOD',
          details: {'method': method},
        );
}

/// Parameters failed validation.
final class InvalidParamsFailure extends Failure {
  // 💎 تم إزالة const من هنا
  InvalidParamsFailure(String detail)
      : super(
          'Invalid parameters',
          code: 'INVALID_PARAMS',
          details: {'detail': detail},
        );
}

/// Network/IO failure (connectivity, DNS, socket).
final class NetworkFailure extends Failure {
  const NetworkFailure(String message) : super(message, code: 'NETWORK');
}

/// Storage failure (disk full, permission denied, path invalid).
final class StorageFailure extends Failure {
  const StorageFailure(String message, {Map<String, Object?>? details})
      : super(message, code: 'STORAGE', details: details);
}
/// Catch-all for unexpected internal errors.
final class InternalFailure extends Failure {
  const InternalFailure(String message, {Map<String, Object?>? details})
      : super(message, code: 'INTERNAL', details: details);
}
