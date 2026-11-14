import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

/// Compares Flutter screenshots while allowing small rasterization variance.
///
/// Keep the tolerance narrow and opt into it only for suites whose committed
/// references are known to differ slightly across CI renderers.
class TolerantLocalFileComparator extends LocalFileComparator {
  TolerantLocalFileComparator(
    super.testFile, {
    required this.pixelDifferenceTolerance,
  }) : assert(pixelDifferenceTolerance >= 0 && pixelDifferenceTolerance <= 1);

  /// Fraction of pixels that may differ (0.0015 = 0.15%).
  final double pixelDifferenceTolerance;

  @override
  Future<bool> compare(Uint8List imageBytes, Uri golden) async {
    final result = await GoldenFileComparator.compareLists(
      imageBytes,
      await getGoldenBytes(golden),
    );
    if (result.passed || result.diffPercent <= pixelDifferenceTolerance) {
      result.dispose();
      return true;
    }

    final failure = await generateFailureOutput(result, golden, basedir);
    result.dispose();
    throw FlutterError(failure);
  }
}
