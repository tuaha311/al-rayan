# Al Rayan — Android app

A deliberately thin app: one activity, one WebView, the storefront at
`alrayan.baseUrl`. There is no second implementation of the shop to keep in
sync — whatever ships to the website ships to the app.

It has no dependencies at all (no AndroidX, no Kotlin), so the APK is a few
hundred KB and builds in seconds.

```
mobile/
  gradle.properties                  alrayan.baseUrl — the site the app opens
  build-apk.sh                       build + copy the APK into static/app/
  app/src/main/
    java/pk/alrayan/app/MainActivity.java
    assets/offline.html              shown when the network is gone
    res/mipmap-*/                    launcher icon + splash logo, from static/images/logo-transparent.png
```

## What the app adds over a browser tab

- Launcher icon and splash with the Al Rayan mark, no browser chrome.
- The site's own mobile layout, at the phone's viewport width, portrait-locked
  (drop `android:screenOrientation` from the manifest to allow rotation).
- Hardware back button walks the site's history.
- `tel:`, `mailto:`, WhatsApp and third-party links hand off to the right app;
  store links stay inside.
- A branded offline page with a retry, instead of Chrome's dinosaur.
- A `AlRayanApp/<version>` User-Agent marker, which the server reads
  (`store/constants.py`) to hide the "download our app" prompt in-app.

## Build

Needs a JDK 17+ — a *JDK*, not the JRE Ubuntu installs by default; without
`javac` Gradle fails with `does not provide the required capabilities:
[JAVA_COMPILER]`. Set `JAVA_HOME` if it is not the system default.

Also needs an Android SDK (platform 35, build-tools 35). Point at it with
`ANDROID_HOME`, or a `mobile/local.properties` holding `sdk.dir=…`.

```bash
./mobile/build-apk.sh          # release build → static/app/al-rayan.apk
cd mobile && ./gradlew assembleDebug    # or a debug build for a device
```

`build-apk.sh` copies the APK to `static/app/al-rayan.apk`, which
`store:download_app` (`/app/download/`) serves to the floating prompt on the
site.

## Signing

`mobile/keystore.properties` and the `.jks` it points at are gitignored. **Back
both up.** Android ties an installed app to its signing key: lose the key and
existing users cannot update, they have to uninstall and reinstall.

```properties
storeFile=al-rayan.jks
storePassword=…
keyAlias=alrayan
keyPassword=…
```

Regenerate one with:

```bash
keytool -genkeypair -keystore mobile/al-rayan.jks -alias alrayan \
        -keyalg RSA -keysize 2048 -validity 10000
```

Without that file the release build is unsigned and `build-apk.sh` refuses to
ship it.

## Releasing a new version

1. Bump `versionCode` (+1) and `versionName` in `app/build.gradle.kts`.
2. Match `ANDROID_APP_VERSION` in `store/constants.py` — it names the
   downloaded file and labels the prompt.
3. `./mobile/build-apk.sh`, then commit the refreshed `static/app/al-rayan.apk`.

Users install over the top; an unchanged `versionCode` will be rejected as a
downgrade.

## Changing the URL

`alrayan.baseUrl` in `gradle.properties` is compiled in as
`BuildConfig.BASE_URL`. Cleartext HTTP is disabled in the manifest, so the host
must be HTTPS (a plain-HTTP LAN box needs
`android:usesCleartextTraffic="true"` for the duration of the test).
