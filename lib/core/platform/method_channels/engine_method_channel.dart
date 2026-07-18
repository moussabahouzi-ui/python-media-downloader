import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../constants/app_constants.dart';
import '../../errors/exceptions.dart';
import 'engine_channel_types.dart';

/// Abstraction over the raw [MethodChannel] so it can be faked in tests.
///
/// The real implementation talks to Kotlin via
/// `com.mediahub.app/engine`. Tests inject a fake that returns canned maps.
abstract class EngineMethodChannel {
  Future<Map<String, Object?>> invoke(BridgeRequest request);

  Stream<BridgeEvent> get events;

  Future<void> dispose();
}

/// Production implementation backed by Flutter's platform channels.
class PlatformEngineMethodChannel implements EngineMethodChannel {
  PlatformEngineMethodChannel({
    MethodChannel? methodChannel,
    EventChannel? eventChannel,
  })  : _method = methodChannel ??
            const MethodChannel(kEngineMethodChannelName),
        _events = eventChannel ??
            const EventChannel(kEngineEventChannelName);

  final MethodChannel _method;
  final EventChannel _events;

  Stream<BridgeEvent>? _eventStream;
  StreamSubscription<dynamic>? _subscription;
  final StreamController<BridgeEvent> _controller =
      StreamController<BridgeEvent>.broadcast();

  static final Random _rng = Random();

  @override
  Future<Map<String, Object?>> invoke(BridgeRequest request) async {
    try {
      final result = await _method.invokeMethod<Map<dynamic, dynamic>>(
        'invoke',
        request.toMap(),
      );
      final map = Map<String, Object?>.from(result ?? const {});
      final ok = map['ok'] as bool? ?? false;
      if (!ok) {
        throw BridgeException(
          code: (map['error']?['code'] as String?) ?? 'INTERNAL',
          message: (map['error']?['message'] as String?) ?? 'Unknown error',
          details: map['error']?['details'] is Map
              ? Map<String, Object?>.from(map['error']!['details'] as Map)
              : null,
        );
      }
      return Map<String, Object?>.from(map['data'] as Map? ?? const {});
    } on PlatformException catch (e) {
      throw BridgeException(
        code: e.code,
        message: e.message ?? 'Platform error',
        details: e.details is Map
            ? Map<String, Object?>.from(e.details as Map)
            : null,
      );
    } on MissingPluginException {
      throw const BridgeException(
        code: 'ENGINE_NOT_READY',
        message: 'Engine bridge is not registered (running outside Android?)',
      );
    }
  }

  @override
  Stream<BridgeEvent> get events {
    _eventStream ??= _events
        .receiveBroadcastStream()
        .map((raw) => BridgeEvent.fromMap(Map<dynamic, dynamic>.from(raw)));
    return _controller.stream;
  }

  /// Wires the raw event channel into our broadcast controller. Called by
  /// [startEventPump]; exposed for the service layer to kick off streaming.
  // ignore: use_setters_to_change_properties
  void pumpEvents(Stream<dynamic> raw) {
    _subscription?.cancel();
    _subscription = raw
        .map((e) => BridgeEvent.fromMap(Map<dynamic, dynamic>.from(e)))
        .listen(_controller.add, onError: _controller.addError);
  }

  @override
  Future<void> dispose() async {
    await _subscription?.cancel();
    _subscription = null;
    await _controller.close();
  }

  /// Generates a random call id (UUIDv4-ish) for correlation.
  static String newCallId() {
    // Simple UUIDv4 generator using Random; sufficient for correlation.
    final b = List<int>.generate(16, (_) => _rng.nextInt(256));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    final hex = b.map((e) => e.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }
}
