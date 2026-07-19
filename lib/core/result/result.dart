/// A sealed [Result] type for explicit, exhaustive error handling.
///
/// Domain operations return `Result<T>` instead of throwing. This forces the
/// presentation layer to handle both branches and keeps error propagation
/// visible in the type system.
library;

import 'package:flutter/foundation.dart';

import '../errors/failures.dart';

@immutable
sealed class Result<T> {
  const Result();

  /// Creates a successful result.
  const factory Result.success(T value) = Success<T>;

  /// Creates a failed result.
  const factory Result.failure(Failure failure) = FailureResult<T>;

  /// `true` when this is a [Success].
  bool get isSuccess => this is Success<T>;

  /// `true` when this is a [FailureResult].
  bool get isFailure => this is FailureResult<T>;

  /// The contained value, or `null` on failure.
  T? get valueOrNull => fold(
        onSuccess: (v) => v,
        onFailure: (_) => null,
      );

  /// The contained failure, or `null` on success.
  Failure? get failureOrNull => fold(
        onSuccess: (_) => null,
        onFailure: (f) => f,
      );

  /// Folds over the two branches.
  R fold<R>({
    required R Function(T value) onSuccess,
    required R Function(Failure failure) onFailure,
  }) {
    final self = this;
    return switch (self) {
      Success<T>(:final value) => onSuccess(value),
      FailureResult<T>(:final failure) => onFailure(failure),
    };
  }

  /// Maps a successful value, leaving failures untouched.
  Result<R> map<R>(R Function(T value) fn) => fold(
        onSuccess: (v) => Result.success(fn(v)),
        onFailure: Result.failure,
      );

  /// Flat-maps a successful value.
  Result<R> flatMap<R>(Result<R> Function(T value) fn) => fold(
        onSuccess: fn,
        onFailure: Result.failure,
      );

  /// Runs [action] on success and returns self.
  Result<T> onSuccess(void Function(T value) action) {
    fold(
      onSuccess: action,
      onFailure: (_) {},
    );
    return this;
  }

  /// Runs [action] on failure and returns self.
  Result<T> onFailure(void Function(Failure failure) action) {
    fold(
      onSuccess: (_) {},
      onFailure: action,
    );
    return this;
  }
}

@immutable
final class Success<T> extends Result<T> {
  const Success(this.value);
  final T value;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Success<T> && runtimeType == other.runtimeType && value == other.value;

  @override
  int get hashCode => Object.hash(runtimeType, value);

  @override
  String toString() => 'Success($value)';
}

@immutable
final class FailureResult<T> extends Result<T> {
  const FailureResult(this.failure);
  final Failure failure;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FailureResult<T> &&
          runtimeType == other.runtimeType &&
          failure == other.failure;

  @override
  int get hashCode => Object.hash(runtimeType, failure);

  @override
  String toString() => 'Failure($failure)';
}
