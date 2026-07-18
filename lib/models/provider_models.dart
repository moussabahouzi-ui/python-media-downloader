import 'package:flutter/foundation.dart';

/// A platform provider's capability descriptor, mirrored from the Python engine.
@immutable
class ProviderInfo {
  const ProviderInfo({
    required this.name,
    required this.displayName,
    required this.engine,
    required this.authRequired,
    required this.maxBatch,
    required this.features,
    required this.urlPatterns,
  });

  factory ProviderInfo.fromMap(Map<String, Object?> map) {
    return ProviderInfo(
      name: map['name'] as String? ?? '',
      displayName: map['displayName'] as String? ?? '',
      engine: map['engine'] as String? ?? '',
      authRequired: map['authRequired'] as bool? ?? false,
      maxBatch: map['maxBatch'] as int? ?? 1,
      features: List<String>.from(map['features'] as List? ?? const []),
      urlPatterns: List<String>.from(map['urlPatterns'] as List? ?? const []),
    );
  }

  final String name;
  final String displayName;
  final String engine;
  final bool authRequired;
  final int maxBatch;
  final List<String> features;
  final List<String> urlPatterns;

  Map<String, Object?> toMap() => {
        'name': name,
        'displayName': displayName,
        'engine': engine,
        'authRequired': authRequired,
        'maxBatch': maxBatch,
        'features': features,
        'urlPatterns': urlPatterns,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ProviderInfo &&
          name == other.name &&
          displayName == other.displayName &&
          engine == other.engine &&
          authRequired == other.authRequired &&
          maxBatch == other.maxBatch;

  @override
  int get hashCode => Object.hash(name, displayName, engine, authRequired, maxBatch);

  @override
  String toString() => 'ProviderInfo($name, engine=$engine, auth=$authRequired)';
}

/// The result of detecting which provider handles a URL.
@immutable
class DetectionResult {
  const DetectionResult({
    required this.provider,
    required this.displayName,
    required this.engine,
    required this.authRequired,
    required this.maxBatch,
  });

  factory DetectionResult.fromMap(Map<String, Object?> map) {
    return DetectionResult(
      provider: map['provider'] as String? ?? '',
      displayName: map['displayName'] as String? ?? '',
      engine: map['engine'] as String? ?? '',
      authRequired: map['authRequired'] as bool? ?? false,
      maxBatch: map['maxBatch'] as int? ?? 1,
    );
  }

  final String provider;
  final String displayName;
  final String engine;
  final bool authRequired;
  final int maxBatch;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DetectionResult && provider == other.provider && engine == other.engine;

  @override
  int get hashCode => Object.hash(provider, engine);

  @override
  String toString() => 'DetectionResult($provider, engine=$engine)';
}

/// Normalized media metadata for a URL.
@immutable
class MediaMetadata {
  const MediaMetadata({
    required this.title,
    this.uploader,
    this.durationSeconds,
    this.thumbnailUrl,
    this.categories = const [],
    this.tags = const [],
    this.extra = const {},
    this.provider = '',
    this.engine = '',
  });

  factory MediaMetadata.fromMap(Map<String, Object?> map) {
    return MediaMetadata(
      title: map['title'] as String? ?? '',
      uploader: map['uploader'] as String?,
      durationSeconds: (map['durationSeconds'] as num?)?.toDouble(),
      thumbnailUrl: map['thumbnailUrl'] as String?,
      categories: List<String>.from(map['categories'] as List? ?? const []),
      tags: List<String>.from(map['tags'] as List? ?? const []),
      extra: Map<String, Object?>.from(map['extra'] as Map? ?? const {}),
      provider: map['provider'] as String? ?? '',
      engine: map['engine'] as String? ?? '',
    );
  }

  final String title;
  final String? uploader;
  final double? durationSeconds;
  final String? thumbnailUrl;
  final List<String> categories;
  final List<String> tags;
  final Map<String, Object?> extra;
  final String provider;
  final String engine;

  @override
  String toString() => 'MediaMetadata(title=$title, uploader=$uploader)';
}
