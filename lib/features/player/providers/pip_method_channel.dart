import 'package:flutter/services.dart';

/// Method channel for Picture-in-Picture control (Android 8.0+).
///
/// Flutter calls [enterPipMode] when the user navigates away from the video
/// player. The Kotlin side calls `enterPictureInPictureMode` on the Activity.
class PipMethodChannel {
  PipMethodChannel()
      : _channel = const MethodChannel('com.mediahub.app/pip');

  final MethodChannel _channel;

  /// Returns `true` if the device supports PiP mode.
  Future<bool> isPipSupported() async {
    try {
      return await _channel.invokeMethod<bool>('isPipSupported') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Requests to enter PiP mode. Returns `true` on success.
  Future<bool> enterPipMode() async {
    try {
      return await _channel.invokeMethod<bool>('enterPipMode') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Returns `true` if the activity is currently in PiP mode.
  Future<bool> isInPipMode() async {
    try {
      return await _channel.invokeMethod<bool>('isInPipMode') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Stream of PiP mode changes. Emits `true` when entering PiP, `false` when
  /// leaving. Uses an event channel under the hood.
  Stream<bool> get pipModeChanges {
    return const EventChannel('com.mediahub.app/pip/events')
        .receiveBroadcastStream()
        .map((e) => e as bool);
  }
}
