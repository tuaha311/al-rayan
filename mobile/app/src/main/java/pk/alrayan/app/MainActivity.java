package pk.alrayan.app;

import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.Toast;

import java.util.Locale;

/**
 * The whole app: one activity hosting the Al Rayan storefront in a WebView.
 *
 * <p>The site is already responsive, so the job here is to stay out of its way —
 * give it the phone viewport, keep store navigation inside the app, and hand
 * anything else (calls, WhatsApp, other sites) to the system.
 */
public class MainActivity extends android.app.Activity {

    /** Anything outside this host opens in the user's browser instead. */
    private static final String HOME_URL = BuildConfig.BASE_URL + "/";

    /** Retry link on the offline page; intercepted rather than run as JS. */
    private static final String RETRY_URL = "alrayan://retry";

    private static final String OFFLINE_URL = "file:///android_asset/offline.html";

    private WebView web;
    private ProgressBar progress;
    private View splash;

    /** True while the offline page is showing, so back/retry behave sensibly. */
    private boolean showingOffline;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        web = findViewById(R.id.web);
        progress = findViewById(R.id.progress);
        splash = findViewById(R.id.splash);

        applySystemBarInsets();
        configureWebView();

        web.setWebViewClient(new StoreWebViewClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setProgress(newProgress);
                progress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }
        });
        web.setDownloadListener(new StoreDownloadListener());

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            load(isOnline() ? HOME_URL : OFFLINE_URL);
        }
    }

    // -----------------------------------------------------------------
    // Setup
    // -----------------------------------------------------------------

    private void configureWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);

        // Render at the width the site's viewport meta asks for — this is what
        // makes the storefront lay out exactly as it does in mobile Chrome.
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);

        // Pinch to zoom on fabric photos, without the dated on-screen controls.
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);

        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMediaPlaybackRequiresUserGesture(false);

        // ANDROID_APP_UA_MARKER in store/constants.py matches on this; keep the
        // two in step or the site will offer the app to people already in it.
        s.setUserAgentString(s.getUserAgentString()
                + " AlRayanApp/" + BuildConfig.VERSION_NAME);

        // The cart and messages ride on the Django session cookie.
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
    }

    /**
     * Android 15 draws apps edge to edge, so pad the content in by the system
     * bars ourselves — otherwise the site header sits under the clock.
     */
    private void applySystemBarInsets() {
        View root = findViewById(R.id.root);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int top, bottom, left, right;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                android.graphics.Insets bars =
                        insets.getInsets(WindowInsets.Type.systemBars()
                                | WindowInsets.Type.displayCutout());
                top = bars.top;
                bottom = bars.bottom;
                left = bars.left;
                right = bars.right;
            } else {
                top = insets.getSystemWindowInsetTop();
                bottom = insets.getSystemWindowInsetBottom();
                left = insets.getSystemWindowInsetLeft();
                right = insets.getSystemWindowInsetRight();
            }
            v.setPadding(left, top, right, bottom);
            return insets;
        });
    }

    private void load(String url) {
        showingOffline = OFFLINE_URL.equals(url);
        web.loadUrl(url);
    }

    private boolean isOnline() {
        ConnectivityManager cm =
                (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) {
            return true;   // can't tell — let the request decide
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            NetworkCapabilities caps = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return caps != null
                    && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        }
        NetworkInfo info = cm.getActiveNetworkInfo();
        return info != null && info.isConnected();
    }

    // -----------------------------------------------------------------
    // Navigation
    // -----------------------------------------------------------------

    private class StoreWebViewClient extends WebViewClient {

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            return handleUrl(request.getUrl());
        }

        @Override
        @SuppressWarnings("deprecation")
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            return handleUrl(Uri.parse(url));
        }

        @Override
        public void onPageStarted(WebView view, String url, Bitmap favicon) {
            progress.setVisibility(View.VISIBLE);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            progress.setVisibility(View.GONE);
            if (splash.getVisibility() == View.VISIBLE) {
                splash.animate().alpha(0f).setDuration(220)
                        .withEndAction(() -> splash.setVisibility(View.GONE));
            }
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request,
                                    WebResourceError error) {
            // Only a failed main document is worth replacing the page for; a
            // missing image or analytics beacon is not.
            if (request.isForMainFrame()) {
                load(OFFLINE_URL);
            }
        }
    }

    /**
     * @return true when the app has taken care of the URL itself.
     */
    private boolean handleUrl(Uri uri) {
        if (RETRY_URL.equals(uri.toString())) {
            load(isOnline() ? HOME_URL : OFFLINE_URL);
            return true;
        }

        String scheme = uri.getScheme() == null
                ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
        boolean isWeb = scheme.equals("http") || scheme.equals("https");
        String host = uri.getHost() == null ? "" : uri.getHost();

        // Our own pages stay in the app; everything else — tel:, mailto:,
        // whatsapp:, other sites — belongs to whatever app owns it.
        if (isWeb && host.equalsIgnoreCase(Uri.parse(HOME_URL).getHost())) {
            return false;
        }
        return openExternally(uri);
    }

    private boolean openExternally(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return true;
        } catch (ActivityNotFoundException e) {
            // No handler installed (no dialler, no WhatsApp). Staying put beats
            // crashing; the WebView will show whatever it can.
            return false;
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (showingOffline) {
            super.onBackPressed();
        } else if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    // -----------------------------------------------------------------
    // Downloads (order slips, size guides — anything the site links to)
    // -----------------------------------------------------------------

    private class StoreDownloadListener implements DownloadListener {
        @Override
        public void onDownloadStart(String url, String userAgent, String contentDisposition,
                                    String mimeType, long contentLength) {
            try {
                String name = URLUtil.guessFileName(url, contentDisposition, mimeType);
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                request.setMimeType(mimeType);
                request.addRequestHeader("User-Agent", userAgent);
                request.setTitle(name);
                request.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(
                        android.os.Environment.DIRECTORY_DOWNLOADS, name);

                DownloadManager dm =
                        (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                if (dm != null) {
                    dm.enqueue(request);
                    Toast.makeText(MainActivity.this, R.string.download_started,
                            Toast.LENGTH_SHORT).show();
                    return;
                }
            } catch (IllegalArgumentException | SecurityException e) {
                // Fall through to the browser below.
            }
            openExternally(Uri.parse(url));
        }
    }
}
