#!/usr/bin/env bash
# Build the Al Rayan Android app and drop the APK where Django serves it.
#
#   ./mobile/build-apk.sh
#
# Requires an Android SDK (ANDROID_HOME or ANDROID_SDK_ROOT, or
# mobile/local.properties) and a JDK 17+. Signing config is optional; see
# mobile/README.md.
set -euo pipefail

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$MOBILE_DIR")"
DEST="$REPO_DIR/static/app/al-rayan.apk"

cd "$MOBILE_DIR"

# A JRE is not enough — the Android plugin needs javac. Ubuntu's default
# `java` package ships without it, which fails deep inside Gradle with a
# "does not provide the required capabilities: [JAVA_COMPILER]" message.
JAVAC="${JAVA_HOME:+$JAVA_HOME/bin/javac}"
if [[ -z "$JAVAC" || ! -x "$JAVAC" ]] && ! command -v javac >/dev/null; then
    echo "error: no JDK found. Install one (e.g. openjdk-17-jdk) and set JAVA_HOME." >&2
    exit 1
fi

./gradlew --no-daemon clean assembleRelease

APK="$MOBILE_DIR/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$APK" ]]; then
    # Without keystore.properties Gradle leaves the build unsigned, and an
    # unsigned APK cannot be installed — fail loudly rather than shipping it.
    echo "error: no signed APK at $APK (is mobile/keystore.properties set up?)" >&2
    ls -l "$MOBILE_DIR/app/build/outputs/apk/release/" >&2 || true
    exit 1
fi

mkdir -p "$(dirname "$DEST")"
cp "$APK" "$DEST"
echo "Shipped $(du -h "$DEST" | cut -f1) → ${DEST#"$REPO_DIR"/}"
echo "Served at /app/download/ — remember to bump versionCode/versionName and"
echo "ANDROID_APP_VERSION in store/constants.py for the next release."
