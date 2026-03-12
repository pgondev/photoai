import flet as ft
import os
import shutil
import sys
import threading
import time
import ctypes
import datetime
import imagehash
from analyzer import ImageAnalyzer
from history_manager import HistoryManager
from settings_manager import SettingsManager
from model_config import MODEL_TIERS, TIER_THRESHOLDS, THRESHOLD_LABELS, THRESHOLD_RANGES, DEFAULT_TIER, get_total_size_mb, format_size
from scripts.download_models import download_tier, get_cache_status

import base64
import io
import cv2
from PIL import Image
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Set AppUserModelID at module level for Windows Taskbar Icon consistency
try:
    myappid = 'PhotoAI.Pro.DesktopApp.V1' # Unique ID
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# Global state to hold scan results
class AppState:
    def __init__(self):
        self.analyzer = None
        self.analyzer_lock = threading.Lock()
        self.hash_groups = {}
        self.scan_complete = False
        
        self.settings_manager = SettingsManager()
        self.source_dir = self.settings_manager.get("source_path", "")
        self.dest_dir = self.settings_manager.get("dest_path", "")
        self.current_theme = self.settings_manager.get("theme", "Dark")
        self.model_tier = self.settings_manager.get("model_tier", DEFAULT_TIER)
        self.thresholds = self.settings_manager.get("thresholds", {})
        
        self.stop_scan_flag = threading.Event()
        self.history_manager = HistoryManager()
        self.empty_folders = []
        self.selected_row = None

state = AppState()

def main(page: ft.Page):
    # --- Theme Logic ---
    def apply_theme(theme_name):
        state.current_theme = theme_name
        state.settings_manager.set("theme", theme_name)

        if theme_name == "Iron Man":
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#121212"
            page.theme = ft.Theme(
                font_family="Orbitron",
                color_scheme=ft.ColorScheme(
                    primary="#FFD700",
                    on_primary="#8B0000",
                    surface="#121212",
                    on_surface="#FFD700",
                    secondary="#00FFFF",
                )
            )
            page.appbar.bgcolor = "#8B0000"
            appbar_title_text.color = "#FFD700"
            ai_status_text.color = "#00FFFF"
            txt_status.color = "#FFD700"
            img_app_logo.src = "/logo_ai_red.png"
            logo_badge.bgcolor = "#6B0000"
            abs_icon_path = os.path.abspath(os.path.join("assets", "logo_ai_red.ico"))
            page.window_icon = abs_icon_path
            try:
                page.window.icon = abs_icon_path
            except Exception: pass
            try:
                txt_source.border_color = "#FFD700"
                txt_source.color = "#FFD700"
                txt_dest.border_color = "#FFD700"
                txt_dest.color = "#FFD700"
                pb_scan.color = "#FFD700"
                pb_scan.bgcolor = "#8B0000"
                tabs.label_color = "#FFD700"
                tabs.indicator_color = "#FFD700"
                tabs.unselected_label_color = "#BDBDBD"
                btn_scan.bgcolor = "#FFD700"
                btn_scan.color = "#8B0000"
                btn_stop.bgcolor = "#8B0000"
                btn_stop.color = "#FFD700"
                btn_del.bgcolor = "#8B0000"
                btn_del.color = "#FFD700"
            except Exception: pass

        elif theme_name == "Dark":
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#0F1117"
            page.theme = ft.Theme(
                font_family=None,
                color_scheme=ft.ColorScheme(
                    primary="#7C6FF7",
                    on_primary="#FFFFFF",
                    surface="#1A1D27",
                    on_surface="#E6EDF3",
                    secondary="#4FC3F7",
                )
            )
            page.appbar.bgcolor = "#1A1D27"
            appbar_title_text.color = "#E6EDF3"
            ai_status_text.color = "#7C6FF7"
            txt_status.color = "#8B90A7"
            img_app_logo.src = "/logo_ai.png"
            logo_badge.bgcolor = "#2D3244"
            abs_icon_path = os.path.abspath(os.path.join("assets", "logo_ai.ico"))
            page.window_icon = abs_icon_path
            try:
                page.window.icon = abs_icon_path
            except Exception: pass
            try:
                txt_source.border_color = "#2D3244"
                txt_source.color = "#E6EDF3"
                txt_dest.border_color = "#2D3244"
                txt_dest.color = "#E6EDF3"
                pb_scan.color = "#7C6FF7"
                pb_scan.bgcolor = "#22262F"
                tabs.label_color = "#7C6FF7"
                tabs.indicator_color = "#7C6FF7"
                tabs.unselected_label_color = "#8B90A7"
                btn_scan.bgcolor = "#7C6FF7"
                btn_scan.color = "#FFFFFF"
                btn_stop.bgcolor = "#EF4444"
                btn_stop.color = "#FFFFFF"
                btn_del.bgcolor = "#EF4444"
                btn_del.color = "#FFFFFF"
            except Exception: pass

        else:
            # Light Theme
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = "#F8F9FC"
            page.theme = ft.Theme(
                font_family=None,
                color_scheme=ft.ColorScheme(
                    primary="#4F46E5",
                    on_primary="#FFFFFF",
                    surface="#FFFFFF",
                    secondary="#06B6D4",
                )
            )
            page.appbar.bgcolor = "#4F46E5"
            appbar_title_text.color = "#FFFFFF"
            ai_status_text.color = "#E0E7FF"
            txt_status.color = "#374151"
            img_app_logo.src = "/logo_ai.png"
            logo_badge.bgcolor = "#3730A3"
            abs_icon_path = os.path.abspath(os.path.join("assets", "logo_ai.ico"))
            page.window_icon = abs_icon_path
            try:
                page.window.icon = abs_icon_path
            except Exception: pass
            try:
                txt_source.border_color = None
                txt_source.color = None
                txt_dest.border_color = None
                txt_dest.color = None
                pb_scan.color = "#4F46E5"
                pb_scan.bgcolor = "#E0E7FF"
                tabs.label_color = "#4F46E5"
                tabs.indicator_color = "#4F46E5"
                tabs.unselected_label_color = ft.Colors.GREY_500
                btn_scan.bgcolor = "#4F46E5"
                btn_scan.color = "#FFFFFF"
                btn_stop.bgcolor = "#EF4444"
                btn_stop.color = "#FFFFFF"
                btn_del.bgcolor = "#EF4444"
                btn_del.color = "#FFFFFF"
            except Exception: pass

        page.update()

    # Window configuration (title will be set after detecting version tag)
    page.padding = ft.padding.only(left=16, right=16, bottom=16, top=0)
    page.window_width = 1200
    page.window_height = 900
    page.window_icon = os.path.abspath(os.path.join("assets", "logo_ai.ico"))
    
    # Detect version tag from executable name or environment variable
    app_title = "PhotoAI Pro"
    try:
        # Check environment variable first (for development testing)
        version_tag = os.environ.get('PHOTOAI_VERSION_TAG', '')
        if version_tag:
            app_title = f"PhotoAI Pro ({version_tag})"
        elif getattr(sys, 'frozen', False):
            # Running as .exe - get the exe name
            exe_name = os.path.basename(sys.executable)
            # Extract version tag if present
            if "(Beta)" in exe_name or "Beta" in exe_name:
                app_title = "PhotoAI Pro (Beta)"
            elif "(Alpha)" in exe_name or "Alpha" in exe_name:
                app_title = "PhotoAI Pro (Alpha)"
            elif "(Dev)" in exe_name or "Dev" in exe_name:
                app_title = "PhotoAI Pro (Dev)"
            elif "(RC)" in exe_name or "RC" in exe_name:
                app_title = "PhotoAI Pro (RC)"
            
            # Check for Lite version
            if "Lite" in exe_name:
                if "(Beta)" in exe_name:
                    app_title = "PhotoAI Pro Lite (Beta)"
                elif "(Alpha)" in exe_name:
                    app_title = "PhotoAI Pro Lite (Alpha)"
                else:
                    app_title = "PhotoAI Pro Lite"
    except Exception:
        pass
    
    # Set window title to match app bar
    page.title = app_title
    
    # Custom Iron Man style font
    page.fonts = {
        "Orbitron": "/Orbitron.ttf"
    }

    # Initial state (set up placeholders first)
    ai_status_icon = ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.YELLOW)
    ai_status_text = ft.Text("AI Loading...", size=12)
    txt_status = ft.Text("", italic=True)
    img_app_logo = ft.Image(src="/logo_ai.png", width=32, height=32, fit=ft.ImageFit.CONTAIN)

    # Badge container — clips the logo and gives it a themed background so it
    # integrates with the app bar instead of showing a raw PNG background.
    logo_badge = ft.Container(
        content=img_app_logo,
        width=40,
        height=40,
        border_radius=10,
        bgcolor="#2D3244",      # updated per theme in apply_theme
        padding=4,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.margin.only(left=8),
    )

    appbar_title_text = ft.Text(app_title, weight=ft.FontWeight.BOLD, size=15)

    page.appbar = ft.AppBar(
        leading=logo_badge,
        leading_width=56,
        title=ft.Column(
            controls=[
                appbar_title_text,
                ft.Row([ai_status_icon, ai_status_text], spacing=4, tight=True),
            ],
            spacing=0,
            tight=True,
        ),
        center_title=False,
        toolbar_height=56,
        actions=[
            ft.IconButton(
                ft.Icons.SETTINGS_OUTLINED,
                on_click=lambda _: open_settings(),
                tooltip="Settings",
            ),
            ft.Container(width=8),
        ],
    )
    
    # Helper for notifications
    def show_snackbar(message, color="#333333"):
        page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    # Define open_settings here
    def open_settings():
        # ── Theme section ──────────────────────────────────────────
        theme_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="Dark", label="Dark (Default)"),
                ft.Radio(value="Light", label="Light"),
                ft.Radio(value="Iron Man", label="Iron Man (HUD)"),
            ]),
            value=state.current_theme,
            on_change=lambda e: apply_theme(e.data)
        )

        # ── AI Models section ──────────────────────────────────────
        cache = get_cache_status()

        def _cache_badge(tier):
            clip_ok = cache[tier]["clip"]
            blip_ok = cache[tier]["blip"]
            if clip_ok and blip_ok:
                return ft.Container(
                    ft.Text("Cached", size=10, color="#4ADE80", weight=ft.FontWeight.W_600),
                    padding=ft.padding.symmetric(vertical=2, horizontal=7),
                    border_radius=10, border=ft.border.all(1, "#4ADE80"),
                )
            size_mb = get_total_size_mb(tier)
            # If CLIP already cached (shared), only caption needs download
            if tier == "modern" and cache["smart"]["clip"]:
                size_mb = MODEL_TIERS["modern"]["blip_size_mb"]
            return ft.Container(
                ft.Text(format_size(size_mb), size=10, color="#FACC15", weight=ft.FontWeight.W_600),
                padding=ft.padding.symmetric(vertical=2, horizontal=7),
                border_radius=10, border=ft.border.all(1, "#FACC15"),
                tooltip="Download needed",
            )

        selected_tier = ft.Ref[str]()
        selected_tier.current = state.model_tier

        tier_cards = {}
        apply_btn = ft.ElevatedButton(
            "Apply", disabled=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        def _make_tier_card(tier_key):
            cfg = MODEL_TIERS[tier_key]
            is_active = (tier_key == state.model_tier)
            card = ft.Container(
                ft.Row([
                    # Left: icon + name + tagline
                    ft.Column([
                        ft.Row([
                            ft.Text(cfg["icon"], size=20),
                            ft.Text(cfg["display_name"], size=14, weight=ft.FontWeight.W_600),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(cfg["tagline"], size=11, color="#A0A8C0"),
                    ], spacing=3, expand=True),
                    # Right: size + cache badge
                    ft.Column([
                        _cache_badge(tier_key),
                        ft.Text(
                            format_size(cfg["clip_size_mb"] + cfg["blip_size_mb"]),
                            size=11, color="#6B7280",
                        ),
                    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=10, horizontal=14),
                border_radius=8,
                border=ft.border.all(2 if is_active else 1, "#7C6FF7" if is_active else "#2D3244"),
                bgcolor="#1A1D27" if is_active else "#13151F",
                on_click=lambda e, k=tier_key: _select_tier(k),
                data=tier_key,
            )
            tier_cards[tier_key] = card
            return card

        def _select_tier(tier_key):
            selected_tier.current = tier_key
            for k, c in tier_cards.items():
                is_sel = (k == tier_key)
                c.border = ft.border.all(2 if is_sel else 1, "#7C6FF7" if is_sel else "#2D3244")
                c.bgcolor = "#1A1D27" if is_sel else "#13151F"
                c.update()
            apply_btn.disabled = (tier_key == state.model_tier and not _thresholds_dirty())
            apply_btn.update()

        # ── Advanced panel ─────────────────────────────────────────
        adv_visible = ft.Ref[bool]()
        adv_visible.current = False
        adv_panel = ft.Column(visible=False, spacing=8)

        # Threshold sliders — keyed by threshold name
        thr_sliders = {}
        thr_labels = {}

        def _thresholds_dirty():
            for key, slider in thr_sliders.items():
                default = TIER_THRESHOLDS[selected_tier.current][key]
                saved = state.thresholds.get(key, default)
                if round(slider.value, 3) != round(saved, 3):
                    return True
            return False

        def _build_adv_panel():
            adv_panel.controls.clear()
            tier_key = selected_tier.current
            cfg = MODEL_TIERS[tier_key]

            # ── Model info table ───────────────────────────────────
            adv_panel.controls.append(ft.Divider(color="#2D3244", height=1))
            adv_panel.controls.append(
                ft.Text("Model Details", size=12, weight=ft.FontWeight.W_600, color="#E0E0E0")
            )

            def _model_row(role, model_id, params, size_mb, tier_k):
                cached = cache[tier_k]["clip"] if role == "CLIP" else cache[tier_k]["blip"]
                badge = ft.Container(
                    ft.Text("Cached" if cached else "Not downloaded", size=10,
                            color="#4ADE80" if cached else "#FACC15",
                            weight=ft.FontWeight.W_600),
                    padding=ft.padding.symmetric(vertical=1, horizontal=6),
                    border_radius=8,
                    border=ft.border.all(1, "#4ADE80" if cached else "#FACC15"),
                )
                return ft.Container(
                    ft.Column([
                        ft.Row([
                            ft.Text(role, size=11, color="#7C6FF7", weight=ft.FontWeight.W_600, width=58),
                            ft.Text(model_id, size=12, weight=ft.FontWeight.W_500, expand=True),
                            badge,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ft.Row([
                            ft.Container(width=58),
                            ft.Text(f"{params}  ·  {format_size(size_mb)}", size=11, color="#6B7280"),
                        ]),
                    ], spacing=2, tight=True),
                    padding=ft.padding.symmetric(vertical=8, horizontal=10),
                    border_radius=6,
                    bgcolor="#13151F",
                )

            adv_panel.controls.append(_model_row(
                "CLIP", cfg["clip_id"], cfg["clip_params"], cfg["clip_size_mb"], tier_key
            ))
            adv_panel.controls.append(_model_row(
                "Caption", cfg["blip_id"], cfg["blip_params"], cfg["blip_size_mb"], tier_key
            ))

            # ── Threshold sliders ──────────────────────────────────
            adv_panel.controls.append(ft.Container(height=4))
            adv_panel.controls.append(
                ft.Row([
                    ft.Text("Detection Thresholds", size=12, weight=ft.FontWeight.W_600, color="#E0E0E0"),
                    ft.TextButton(
                        "Reset to defaults",
                        style=ft.ButtonStyle(padding=ft.padding.all(0)),
                        on_click=_reset_thresholds,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

            thr_sliders.clear()
            thr_labels.clear()
            for key, label in THRESHOLD_LABELS.items():
                lo, hi = THRESHOLD_RANGES[key]
                saved = state.thresholds.get(key, TIER_THRESHOLDS[tier_key][key])
                lbl = ft.Text(f"{saved:.2f}", size=12, color="#7C6FF7", weight=ft.FontWeight.W_600)
                thr_labels[key] = lbl

                def _on_thr_change(e, k=key):
                    thr_labels[k].value = f"{e.control.value:.2f}"
                    thr_labels[k].update()
                    apply_btn.disabled = (selected_tier.current == state.model_tier and not _thresholds_dirty())
                    apply_btn.update()

                slider = ft.Slider(
                    min=lo, max=hi, value=saved, divisions=int((hi - lo) * 100),
                    on_change=_on_thr_change,
                    active_color="#7C6FF7", thumb_color="#7C6FF7",
                    expand=True, height=32,
                )
                thr_sliders[key] = slider
                adv_panel.controls.append(
                    ft.Container(
                        ft.Column([
                            ft.Row([
                                ft.Text(label, size=12, color="#A0A8C0", expand=True),
                                lbl,
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            slider,
                        ], spacing=0, tight=True),
                        padding=ft.padding.only(bottom=4),
                    )
                )

        def _reset_thresholds(_):
            tier_key = selected_tier.current
            for key, slider in thr_sliders.items():
                default = TIER_THRESHOLDS[tier_key][key]
                slider.value = default
                thr_labels[key].value = f"{default:.2f}"
            adv_panel.update()
            apply_btn.disabled = (tier_key == state.model_tier and not _thresholds_dirty())
            apply_btn.update()

        adv_toggle = ft.TextButton(
            "Show technical details ▼",
            style=ft.ButtonStyle(padding=ft.padding.all(0)),
        )

        def _toggle_adv(_):
            adv_visible.current = not adv_visible.current
            if adv_visible.current:
                _build_adv_panel()
                adv_panel.visible = True
                adv_toggle.text = "Hide technical details ▲"
            else:
                adv_panel.visible = False
                adv_toggle.text = "Show technical details ▼"
            adv_panel.update()
            adv_toggle.update()

        adv_toggle.on_click = _toggle_adv

        # ── Download progress ──────────────────────────────────────
        dl_progress = ft.ProgressBar(value=0, visible=False, expand=True, height=4, color="#7C6FF7")
        dl_status = ft.Text("", size=11, color="#A0A8C0", visible=False)

        # ── Apply logic ────────────────────────────────────────────
        def _apply(e):
            new_tier = selected_tier.current
            new_thresholds = {k: round(s.value, 3) for k, s in thr_sliders.items()} if thr_sliders else state.thresholds

            # Save thresholds immediately
            state.thresholds = new_thresholds
            state.settings_manager.set("thresholds", new_thresholds)

            tier_changed = (new_tier != state.model_tier)

            if tier_changed:
                state.model_tier = new_tier
                state.settings_manager.set("model_tier", new_tier)

                # Check if download needed
                c = get_cache_status()
                needs_download = not (c[new_tier]["clip"] and c[new_tier]["blip"])

                if needs_download:
                    dl_progress.visible = True
                    dl_status.visible = True
                    apply_btn.disabled = True
                    dl_progress.update()
                    dl_status.update()
                    apply_btn.update()

                    def _do_download():
                        def _cb(msg):
                            dl_status.value = msg
                            dl_status.update()
                        ok = download_tier(new_tier, progress_cb=_cb)
                        dl_progress.visible = False
                        dl_status.visible = False
                        dl_progress.update()
                        dl_status.update()
                        if ok:
                            _reload_analyzer()

                    threading.Thread(target=_do_download, daemon=True).start()
                    return

            if tier_changed or new_thresholds != state.thresholds:
                _reload_analyzer()

            apply_btn.disabled = True
            apply_btn.update()

        def _reload_analyzer():
            state.analyzer = None
            ai_status_icon.name = ft.Icons.SYNC
            ai_status_text.value = "Reloading AI..."
            ai_status_icon.color = "#FACC15"
            ai_status_text.color = "#FACC15"
            page.update()
            threading.Thread(target=init_ai_background, daemon=True).start()

        apply_btn.on_click = _apply

        # ── Assemble dialog ────────────────────────────────────────
        tier_col = ft.Column(
            [_make_tier_card(t) for t in MODEL_TIERS],
            spacing=6,
        )

        dg = ft.AlertDialog(
            title=ft.Text("Settings", size=18, weight=ft.FontWeight.W_600),
            content=ft.Container(
                ft.Column([
                    # ── AI Models ──────────────────────────────────
                    ft.Text("AI Models", weight=ft.FontWeight.W_700, size=13, color="#E0E0E0"),
                    ft.Container(height=4),
                    tier_col,
                    ft.Container(height=2),
                    adv_toggle,
                    adv_panel,
                    # Download progress (hidden until needed)
                    ft.Container(
                        ft.Column([
                            dl_progress,
                            dl_status,
                        ], spacing=4, tight=True),
                        visible=True,
                    ),
                    ft.Divider(color="#2D3244", height=20),
                    # ── Interface Theme ─────────────────────────────
                    ft.Text("Interface Theme", weight=ft.FontWeight.W_700, size=13, color="#E0E0E0"),
                    ft.Container(height=4),
                    theme_radio,
                ], tight=True, spacing=4, scroll=ft.ScrollMode.AUTO),
                width=480,
                height=500,
                padding=ft.padding.only(right=8),
            ),
            actions=[
                apply_btn,
                ft.TextButton("Close", on_click=lambda _: page.close(dg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dg)

    # Initial theme will be applied later

    # --- Pickers ---
    # We need separate pickers for Source and Dest to easier handle callbacks
    fp_source = ft.FilePicker()
    fp_dest = ft.FilePicker()

    def on_source_result(e: ft.FilePickerResultEvent):
        if e.path:
            txt_source.value = e.path
            state.settings_manager.set("source_path", e.path)
            txt_source.update()
    
    def on_dest_result(e: ft.FilePickerResultEvent):
        if e.path:
            txt_dest.value = e.path
            state.settings_manager.set("dest_path", e.path)
            txt_dest.update()

    def on_txt_source_change(e):
        state.settings_manager.set("source_path", e.control.value)

    def on_txt_dest_change(e):
        state.settings_manager.set("dest_path", e.control.value)

    fp_source.on_result = on_source_result
    fp_dest.on_result = on_dest_result
    page.overlay.extend([fp_source, fp_dest])

    # Lazy load analyzer
    def get_analyzer():
        with state.analyzer_lock:
            if state.analyzer is None:
                state.analyzer = ImageAnalyzer(
                    tier=state.model_tier,
                    threshold_overrides=state.thresholds or None,
                )
        return state.analyzer

    # Background Init Task
    def init_ai_background():
        get_analyzer() # Triggers the lazy load
        ai_status_icon.name = ft.Icons.AUTO_AWESOME
        ai_status_text.value = "JARVIS ACTIVE"
        # Theme colors will be applied by apply_theme
        if state.current_theme == "Iron Man":
            ai_status_icon.color = "#00FFFF"
            ai_status_text.color = "#00FFFF"
        else:
            ai_status_icon.color = ft.Colors.GREEN
            ai_status_text.color = ft.Colors.BLACK if page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.WHITE
        
        # Show main UI (already visible by default now)
        page.update()

    # Start background init immediately
    threading.Thread(target=init_ai_background, daemon=True).start()

    # --- Pickers & TextFields ---
    saved_src = state.settings_manager.get("source_path", "")
    saved_dst = state.settings_manager.get("dest_path", "")
    
    txt_source = ft.TextField(label="Source Folder", value=saved_src, expand=True, dense=True, on_change=on_txt_source_change)
    txt_dest = ft.TextField(label="Destination Folder", value=saved_dst, expand=True, dense=True, on_change=on_txt_dest_change)

    btn_browse_src = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: fp_source.get_directory_path())
    btn_browse_dest = ft.IconButton(icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: fp_dest.get_directory_path())

    # 3. Progress & Status
    pb_scan = ft.ProgressBar(value=0, visible=False, expand=True, height=6)

    # 4. Containers
    col_find_dups = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    col_organize = ft.Column(expand=True)
    col_history = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    col_results = ft.Column()
    col_help = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    col_about = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    # --- LOGIC: STOP SCAN ---
    def stop_scan(e):
        if not state.stop_scan_flag.is_set():
            state.stop_scan_flag.set()
            txt_status.value = "Stopping..."
            txt_status.update()

    # --- LOGIC: START SCAN ---
    def start_scan(e):
        src = txt_source.value
        dst = txt_dest.value
        state.source_dir = src
        state.dest_dir = dst
        
        # Validation Alerts
        if not src or not os.path.exists(src):
            error_dlg = ft.AlertDialog(
                title=ft.Text("Source Folder Missing"),
                content=ft.Text(f"The source folder '{src}' does not exist. Please select a valid folder."),
                actions=[ft.TextButton("OK", on_click=lambda _: page.close(error_dlg))]
            )
            page.open(error_dlg)
            return

        if not dst or not os.path.exists(dst):
            error_dlg_dst = ft.AlertDialog(
                title=ft.Text("Destination Folder Missing"),
                content=ft.Text(f"The destination folder '{dst}' does not exist. Please select a valid folder."),
                actions=[ft.TextButton("OK", on_click=lambda _: page.close(error_dlg_dst))]
            )
            page.open(error_dlg_dst)
            return
        # Reset state
        state.scan_complete = False
        state.stop_scan_flag.clear()
        state.empty_folders.clear()  # Clear old empty folders from previous scan
        state.empty_folders_set = set()  # Clear the helper set as well
        col_results.controls.clear()
        
        # UI Updates
        btn_scan.disabled = True
        btn_scan.visible = False
        btn_stop.visible = True
        btn_stop.disabled = False
        btn_del.visible = False
        pb_scan.visible = True
        pb_scan.value = None
        txt_status.value = "Initializing AI Models..."
        page.update()

        def scan_task():
            try:
                analyzer = get_analyzer()
                
                # File Types
                img_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
                vid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
                aud_exts = {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
                doc_exts = {'.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.doc'}

                files = []
                for root, dirs, f in os.walk(src):
                    for file in f:
                        # Allow ALL files to be scanned, so "Other" category works
                        files.append(os.path.join(root, file))
                
                if not files:
                    txt_status.value = "No supported files found."
                    return

                state.hash_groups = {}
                count = len(files)
                state.history_manager.add_entry("Scan Started", f"Source: {src}, Files: {count}")
                
                for i, file_path in enumerate(files):
                    if state.stop_scan_flag.is_set():
                        txt_status.value = "Scan stopped by user."
                        state.history_manager.add_entry("Scan Stopped", "User interrupted scan.")
                        break

                    # Update Progress
                    prog = (i + 1) / count
                    pb_scan.value = prog
                    txt_status.value = f"Analyzing {i+1}/{count}: {os.path.basename(file_path)}"
                    page.update()
                    
                    ext = os.path.splitext(file_path)[1].lower()
                    
                    # LOGIC:
                    # 1. Images: Dupe Check + Quality + Doc-Check
                    # 2. Others: Just add to simple list or pseudo-hash group with unique key
                    


                    if ext in img_exts:
                        phash = analyzer.calculate_phash(file_path)
                        chash = analyzer.calculate_colorhash(file_path)
                        
                        if phash and chash:
                            # ... (existing matching logic) ...
                            # FUZZY SEARCH logic matches matches
                            target_group_key = None
                            h1 = imagehash.hex_to_hash(phash)
                            
                            for existing_key in state.hash_groups.keys():
                                if existing_key.startswith("unique_"): continue
                                if "_" not in existing_key: continue
                                
                                parts = existing_key.split("_")
                                if len(parts) != 2: continue
                                
                                ex_p, ex_c = parts
                                
                                try:
                                    h2 = imagehash.hex_to_hash(ex_p)
                                    c1 = imagehash.hex_to_hash(chash)
                                    c2 = imagehash.hex_to_hash(ex_c)
                                    
                                    phash_dist = h1 - h2
                                    chash_dist = c1 - c2
                                    
                                    if phash_dist <= 8 and chash_dist <= 5:
                                        target_group_key = existing_key
                                        break
                                except Exception: continue
                            
                            composite_key = target_group_key if target_group_key else f"{phash}_{chash}"
                            if composite_key not in state.hash_groups:
                                state.hash_groups[composite_key] = []
                            
                            quality = analyzer.analyze_quality(file_path)
                            tags = analyzer.generate_tags(file_path)
                            
                            is_doc = analyzer.is_document_image(file_path)
                            is_pii = analyzer.is_pii_document(file_path)
                            is_fwd_meta = analyzer.is_likely_forward(file_path)
                            is_meme = analyzer.is_meme_or_screenshot(file_path)
                            is_ss_visual = analyzer.is_screenshot(file_path)
                            is_ss_name = "screenshot" in os.path.basename(file_path).lower() or "screen shot" in os.path.basename(file_path).lower()
                            is_screenshot = is_ss_visual or is_ss_name
                            is_fwd = (is_fwd_meta or is_meme) and not is_screenshot

                            dob = analyzer.get_exif_date(file_path)
                            state.hash_groups[composite_key].append({
                                "path": file_path,
                                "phash": composite_key,
                                "quality": quality,
                                "tags": tags,
                                "type": "image",
                                "dob": dob,
                                "is_doc": is_doc,
                                "is_pii": is_pii,
                                "is_fwd": is_fwd,
                                "is_fwd_meta": is_fwd_meta,
                                "is_meme_visual": is_meme,
                                "is_screenshot": is_screenshot,
                                "is_forward_visual": analyzer.is_likely_forward_visual(file_path)
                            })
                        else:
                            # Handling for corrupt/unreadable images (phash is None)
                            # Treat as "Other" so user can see/delete them
                            unique_key = f"unique_{file_path}"
                            
                            # Try to get date if possible, else None
                            dob = analyzer.get_exif_date(file_path)
                            state.hash_groups[unique_key] = [{
                                "path": file_path,
                                "phash": unique_key,
                                "quality": {"overall": 0},
                                "tags": ["Unreadable/Corrupt Image"],
                                "type": "other",
                                "dob": dob
                            }]

                    else:
                        # Unknown / Other files
                        unique_key = f"unique_{file_path}"
                        file_type = "other"
                        if ext in vid_exts: file_type = "video"
                        elif ext in aud_exts: file_type = "audio"
                        elif ext in doc_exts: file_type = "document"
                        
                        dob = analyzer.get_exif_date(file_path)
                        state.hash_groups[unique_key] = [{
                            "path": file_path,
                            "phash": unique_key,
                            "quality": {"overall": 0}, # Dummy
                            "tags": [],
                            "type": file_type,
                            "dob": dob
                        }]
                
                if not state.stop_scan_flag.is_set():
                    # ALWAYS scan for empty folders
                    state.empty_folders.clear()
                    ignored_files = {'thumbs.db', 'desktop.ini', '.ds_store'}
                    state.empty_folders_set = set() # Helper for O(1) lookup
                    for root, dirs, f in os.walk(state.source_dir, topdown=False): # Bottom up to catch nested empties
                        # Filter out ignored files
                        valid_files = [x for x in f if x.lower() not in ignored_files]
                        
                        # Check if all subdirectories are known to be empty
                        are_all_subdirs_empty = True
                        for d in dirs:
                            full_path = os.path.join(root, d)
                            if full_path not in state.empty_folders_set:
                                are_all_subdirs_empty = False
                                break

                        if not valid_files and are_all_subdirs_empty:
                            state.empty_folders.append(root)
                            state.empty_folders_set.add(root)
                                
                    duplicates = [len(g) for g in state.hash_groups.values() if len(g) > 1]
                    
                    state.scan_complete = True
                    txt_status.value = f"Scan Complete. Found {len(files)} files."
                    if state.empty_folders:
                        txt_status.value += f" Found {len(state.empty_folders)} empty folders."
                        
                    state.history_manager.add_entry("Scan Complete", f"Scanned {len(files)} files. Found {len(state.empty_folders)} empty folders.")
                    
                    if duplicates or state.empty_folders:
                        # Show delete button if we have dupes OR empty folders (and user can check empty box)
                        # Actually if only empty folders, we might need logic adjustment
                        btn_del.visible = True
                    page.update() # FORCE UPDATE HERE
                    show_cleanup_grid(None) # Auto-Show Grid (only dupes usually)
                    
                    # Also refresh Organize tab
                    refresh_organize_tab()
                    refresh_history_tab()

            except Exception as ex:
                txt_status.value = f"Error: {ex}"
                print(ex)
            finally:
                btn_scan.disabled = False
                btn_scan.visible = True
                btn_stop.visible = False
                btn_stop.disabled = True
                pb_scan.visible = False
                page.update()

        t = threading.Thread(target=scan_task)
        t.start()

    # --- Helper: Get Displayable Image Source (Shared) ---
    def get_display_src(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in {'.heic', '.heif'}:
            try:
                # Convert HEIC to small JPEG base64 for display
                # We use 200x200 thumbnail to keep it fast
                img = Image.open(path)
                img.thumbnail((300, 300)) # Increased size slightly for preview pane
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                buff = io.BytesIO()
                img.save(buff, format="JPEG", quality=70)
                b64_str = base64.b64encode(buff.getvalue()).decode('utf-8')
                return None, b64_str # Returns (src, src_base64)
            except Exception as e:
                if "cannot identify image file" in str(e):
                    print(f"Skipping unrecognized file format for HEIC preview: {os.path.basename(path)}")
                else:
                    print(f"Error converting HEIC preview {os.path.basename(path)}: {e}")
                return "assets/logo_ai.png", None
        return path, None

    def get_video_thumbnail(path):
        """Extract a thumbnail from 10% into the video using OpenCV."""
        try:
            cap = cv2.VideoCapture(path)
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if total_frames > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * 0.1))
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            h, w = frame.shape[:2]
            scale = min(300 / w, 300 / h)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame)
            buff = io.BytesIO()
            pil_img.save(buff, format="JPEG", quality=70)
            return base64.b64encode(buff.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"Error extracting video thumbnail for {os.path.basename(path)}: {e}")
            return None

    # --- LOGIC: RENDER CLEANUP GRID ---
    checkboxes_to_delete = {} 

    def show_cleanup_grid(e):
        col_results.controls.clear()
        checkboxes_to_delete.clear()
        
        duplicates = [g for g in state.hash_groups.values() if len(g) > 1]
        
        if not duplicates and not state.empty_folders:

            col_results.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color="green", size=50),
                        ft.Text("No duplicates or empty folders found!", size=20)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    padding=20
                )
            )
        else:
            if duplicates:
                col_results.controls.append(ft.Text(f"Found {len(duplicates)} duplicate groups.", size=18, weight=ft.FontWeight.BOLD))
            
            # Theme colors
            if state.current_theme == "Iron Man":
                block_bg = "#1A1A1A"
                block_border = "#8B0000"
            elif state.current_theme == "Dark":
                block_bg = "#1A1D27"
                block_border = "#2D3244"
            else:
                block_bg = "#FFFFFF"
                block_border = "#E0E7FF"

            # --- 1. Empty Folders Group ---
            if state.empty_folders:
                # Force visibility of the main checkbox
                chk_del_empty.visible = True
                chk_del_empty.label = f"Also delete {len(state.empty_folders)} empty folders"
                chk_del_empty.update()
                
                col_results.controls.append(ft.Text(f"Found {len(state.empty_folders)} empty folders.", size=18, weight=ft.FontWeight.BOLD, color="orange"))
                
                row_empty = ft.Row(scroll=ft.ScrollMode.ALWAYS)
                
                for folder_path in state.empty_folders:
                    chk = ft.Checkbox(label="Delete", value=True, fill_color="red")
                    # Use a unique key prefix for folders to avoid collision (though unlikely)
                    checkboxes_to_delete[f"folder::{folder_path}"] = chk
                    
                    card = ft.Container(
                        width=250,
                        padding=10,
                        border=ft.border.all(1, ft.Colors.ORANGE),
                        border_radius=8,
                        content=ft.Column([
                            ft.Icon(ft.Icons.FOLDER_OFF, color="orange", size=30),
                            ft.Text(os.path.basename(folder_path), weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(folder_path, size=10, color=ft.Colors.GREY, selectable=True),
                            chk
                        ], spacing=5)
                    )
                    row_empty.controls.append(card)

                col_results.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("Empty Folders", weight=ft.FontWeight.BOLD),
                        row_empty,
                        ft.Divider()
                    ]),
                    bgcolor=block_bg,
                    padding=15,
                    border=ft.border.all(1, block_border),
                    border_radius=10,
                    margin=10
                ))

            col_results.controls.append(ft.Text("Select items to trash.", size=16))

            # --- 2. Duplicate Groups ---
            for i, group in enumerate(duplicates):
                # Filter out files that might have been deleted/moved
                group = [item for item in group if os.path.exists(item['path'])]
                if len(group) < 2: continue # No longer duplicate

                tags = group[0]['tags']
                tag_str = ", ".join(tags) if tags else "No tags"
                
                best_shot_idx = max(range(len(group)), key=lambda x: group[x]['quality']['overall'])
                
                row_imgs = ft.Row(scroll=ft.ScrollMode.ALWAYS)
                
                for idx, item in enumerate(group):
                    is_best = (idx == best_shot_idx)
                    quality = item['quality']['overall']
                    
                    chk = ft.Checkbox(label="Trash", value=(not is_best), fill_color="red")
                    checkboxes_to_delete[item['path']] = chk
                    
                    # Compute border color
                    border_col = ft.Colors.GREEN if is_best else ft.Colors.GREY_400

                    # Resolve Image Source (HEIC fix)
                    src_path, src_b64 = get_display_src(item['path'])

                    card = ft.Container(
                        width=220,
                        padding=10,
                        border=ft.border.all(3 if is_best else 1, border_col),
                        border_radius=8,
                        content=ft.Column([
                            ft.Image(
                                src=src_path if src_path else "", 
                                src_base64=src_b64,
                                width=200, 
                                height=180, 
                                fit=ft.ImageFit.CONTAIN
                            ),
                            ft.Text(f"Score: {quality:.1f}", weight=ft.FontWeight.BOLD if is_best else ft.FontWeight.NORMAL),
                            ft.Text(f"Blur: {item['quality']['blur']:.0f} | Smile: {item['quality']['smile']:.0f}", size=10, color=ft.Colors.GREY),
                            ft.Container(
                                content=ft.Text("✨ BEST" if is_best else "", color="white", size=10),
                                bgcolor="green" if is_best else None,
                                padding=ft.padding.symmetric(horizontal=5),
                                border_radius=4,
                            ),
                            chk
                        ], spacing=2)
                    )
                    row_imgs.controls.append(card)
                
                col_results.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"Group {i+1}: {tag_str}", weight=ft.FontWeight.BOLD),
                        row_imgs,
                        ft.Divider()
                    ]),
                    bgcolor=block_bg,
                    padding=15,
                    border=ft.border.all(1, block_border),
                    border_radius=10,
                    margin=10
                ))

        page.update()


    # --- LOGIC: DELETE SELECTED ---
    def delete_selected(e):
        # Separate files and folders
        files_to_delete = []
        folders_to_delete = []

        for key, chk in checkboxes_to_delete.items():
            if chk.value:
                if key.startswith("folder::"):
                    # Extract path from key "folder::/path/to/folder"
                    folders_to_delete.append(key.replace("folder::", ""))
                else:
                    files_to_delete.append(key)
        
        # If user unchecks the global "empty" box, maybe we should ignore folders? 
        # But logic is clearer if checkboxes rule. 
        # Let's say if chk_del_empty is VISIBLE and UNCHECKED, we skip folders?
        # User requested "checkbox next to trash button".
        # If that is unchecked, we should probably safeguard folders even if they are selected in grid.
        # But that's confusing.
        # Better: Global checkbox toggles 'Select All' for folders? 
        # For now: We rely on the INDIVIDUAL checkboxes in the grid, as that gave granular control.
        # But to respect the request "bring back the checkbox", let's use it as a safety gate.
        
        if chk_del_empty.visible and not chk_del_empty.value:
             folders_to_delete = [] # Safety: Don't delete folders if master switch is off
            
        if not files_to_delete and not folders_to_delete:
            page.open(ft.SnackBar(ft.Text("No items selected for deletion.")))
            return
        
        trash_dir = os.path.join(state.dest_dir, "Trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        # CRITICAL: Clear image cache to release file handles
        # The analyzer's _get_image uses @lru_cache which keeps files open
        if state.analyzer:
            state.analyzer._get_image.cache_clear()
            state.analyzer._get_embedding_tensor.cache_clear()
        
        def _do_delete():
            # Give Windows a moment to release file handles
            time.sleep(0.5)

            count_files = 0
            count_folders = 0
            log_entries = []

            # 1. Delete Files
            for path in files_to_delete:
                try:
                    dest = os.path.join(trash_dir, os.path.basename(path))
                    # Collision guard: rename if a file with the same name already exists in Trash
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(dest)
                        i = 1
                        while os.path.exists(f"{base}_{i}{ext}"):
                            i += 1
                        dest = f"{base}_{i}{ext}"
                    shutil.move(path, dest)
                    log_entries.append(f"Moved to Trash: {path} -> {dest}")
                    count_files += 1
                except Exception as ex:
                    log_entries.append(f"Error moving {path}: {ex}")
                    print(f"Error moving {path}: {ex}")

            # 2. Delete Empty Folders
            for path in folders_to_delete:
                try:
                    if os.path.isdir(path):
                        os.rmdir(path)
                        log_entries.append(f"Deleted Empty Folder: {path}")
                        count_folders += 1
                except Exception as ex:
                    log_entries.append(f"Error deleting folder {path}: {ex}")
                    print(f"Error deleting folder {path}: {ex}")

            total = count_files + count_folders
            state.history_manager.add_entry("Cleanup", f"Moved {count_files} files, Deleted {count_folders} folders.", log_content=log_entries)

            # Reset empty list if we deleted them
            if count_folders > 0:
                state.empty_folders = [f for f in state.empty_folders if f not in folders_to_delete]
                if not state.empty_folders:
                    chk_del_empty.visible = False

            # 3. Update Hash Groups (Remove deleted files)
            if count_files > 0:
                deleted_set = set(files_to_delete)
                for key in list(state.hash_groups.keys()):
                    group = state.hash_groups[key]
                    new_group = [item for item in group if item['path'] not in deleted_set]
                    state.hash_groups[key] = new_group
                    if len(new_group) == 0:
                        del state.hash_groups[key]

            # 4. Refresh UI
            refresh_organize_tab()
            dlg_done = ft.AlertDialog(
                title=ft.Text("Cleanup Complete"),
                content=ft.Text(f"Successfully cleaned up {total} items.\n({count_files} files, {count_folders} folders)"),
                actions=[ft.TextButton("Close", on_click=lambda e: page.close(dlg_done))]
            )
            page.open(dlg_done)
            show_cleanup_grid(None)
            refresh_history_tab()
            page.update()

        threading.Thread(target=_do_delete, daemon=True).start()

    # --- CONTROLS DEFINITION ---
    _btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        elevation=2,
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
    )
    btn_scan = ft.ElevatedButton(
        "Start Scan",
        icon=ft.Icons.PLAY_ARROW,
        on_click=start_scan,
        height=42,
        style=_btn_style,
    )
    btn_stop = ft.ElevatedButton(
        "Stop",
        icon=ft.Icons.STOP,
        on_click=stop_scan,
        height=42,
        disabled=True,
        visible=False,
        style=_btn_style,
    )

    # "Move to Trash" button (hidden until scan complete)
    btn_del = ft.ElevatedButton(
        "Move to Trash",
        icon=ft.Icons.DELETE_OUTLINE,
        on_click=delete_selected,
        visible=False,
        height=42,
        style=_btn_style,
    )

    # Checkbox for empty folders (Only visible after scan if empties found)
    chk_del_empty = ft.Checkbox(label="Delete Empty Folders", value=False, visible=False, fill_color="red")

    # --- TAB 1 LAYOUT: Find Duplicates ---
    col_find_dups.controls.extend([
        ft.Text("SELECT FOLDERS", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.GREY_500),
        ft.Container(height=4),
        ft.Row([
            ft.Row([txt_source, btn_browse_src], expand=True, spacing=6),
            ft.Container(width=12),
            ft.Row([txt_dest, btn_browse_dest], expand=True, spacing=6),
        ], spacing=0),
        # Removed chk_find_empty from here
        ft.Row([
            ft.Row([btn_scan, btn_stop, btn_del, chk_del_empty], spacing=8),
            ft.Container(width=16),
            ft.Column([
                pb_scan,
                txt_status,
            ], spacing=4, tight=True, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
        ft.Divider(),
        col_results
    ])


    # --- TAB 2: ORGANIZE ---
    chk_move_others = ft.Checkbox(label="Move non-image files to 'Other Files'", value=True)
    
    def refresh_organize_tab():
        col_organize.controls.clear()
        if not state.scan_complete:
            col_organize.controls.append(ft.Text("Please run a scan first.", italic=True))
        else:
            # Count valid files
            total_items = 0
            for g in state.hash_groups.values():
                for item in g:
                     if os.path.exists(item['path']):
                         total_items += 1
            
            status_txt = ft.Text(f"Ready to organize {total_items} remaining photos.", size=14, italic=True, color=ft.Colors.BLUE_GREY)

            # Define run_organize early to avoid UnboundLocalError
            def run_organize(e):
                processed = 0
                others = 0
                cat_counts = {"Trash": 0, "Personal": 0, "Memes": 0, "Forwards": 0, "Videos": 0, "Audios": 0, "Documents": 0, "Images": 0}

                movement_log = []
                for item in all_files:
                    path = item['src']
                    if not os.path.exists(path): continue
                    
                    cat = item.get('category')
                    if not cat: continue 
                    
                    # Write AI tags to EXIF before moving (only for JPEG images)
                    tags = item.get('tags', [])
                    if tags and path.lower().endswith(('.jpg', '.jpeg')):
                        try:
                            analyzer = get_analyzer()
                            analyzer.write_tags_to_exif(path, tags)
                        except Exception as tag_err:
                            print(f"Warning: Could not write tags to {path}: {tag_err}")
                        
                    try:
                        if cat in cat_counts:
                            cat_counts[cat] += 1
                        else:
                            cat_counts["Images"] += 1
                            
                        target_path = os.path.join(state.dest_dir, item.get('dest', 'Images/Unknown'))
                        target_dir = os.path.dirname(target_path)
                        os.makedirs(target_dir, exist_ok=True)

                        if target_path:
                            # Collision guard: rename if destination already exists
                            if os.path.exists(target_path):
                                base, ext = os.path.splitext(target_path)
                                i = 1
                                while os.path.exists(f"{base}_{i}{ext}"):
                                    i += 1
                                target_path = f"{base}_{i}{ext}"
                            shutil.move(path, target_path)
                            movement_log.append(f"Moved: {path} -> {target_path}")
                            processed += 1

                    except Exception as err:
                        movement_log.append(f"Error moving {path}: {err}")
                        print(f"Error moving {path}: {err}")
                
                if chk_move_others.value:
                    # Supported Extensions from scan_task
                    img_exts = {'.jpg', '.jpeg', '.png', '.webp'}
                    vid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
                    aud_exts = {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
                    doc_exts = {'.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.doc'}
                    
                    supported = img_exts | vid_exts | aud_exts | doc_exts
                    
                    other_dir = os.path.join(state.dest_dir, "Other Files")
                    os.makedirs(other_dir, exist_ok=True)
                    for root, dirs, f in os.walk(state.source_dir):
                        for file in f:
                            if not any(file.lower().endswith(ext) for ext in supported):
                                try:
                                    src_p = os.path.join(root, file)
                                    dst_p = os.path.join(other_dir, file)
                                    shutil.move(src_p, dst_p)
                                    movement_log.append(f"Moved (Other): {src_p} -> {dst_p}")
                                    others += 1
                                except Exception: pass
                
                details = ", ".join([f"{k}: {v}" for k, v in cat_counts.items() if v > 0])
                if others > 0: details += f", Others: {others}"
                
                state.history_manager.add_entry("Organize Complete", f"Processed {processed} items. [{details}]", log_content=movement_log)
                success_dlg = ft.AlertDialog(
                    title=ft.Text("Organization Complete"),
                    content=ft.Column([
                        ft.Text("Your photos have been successfully sorted.", weight=ft.FontWeight.BOLD),
                        ft.Text(f"Summary: {details}"),
                        ft.Text(f"Total processed: {processed + others} items.")
                    ], tight=True),
                    actions=[ft.TextButton("View History", on_click=lambda _: (setattr(tabs, 'selected_index', 2), page.close(success_dlg), page.update()))]
                )
                page.open(success_dlg)
                refresh_history_tab()
                page.update()
            
            # --- PREVIEW GENERATION ---
            all_files = [] # Flat list for table

            
            def open_file(e):
                try:
                    os.startfile(e.control.data)
                except Exception as ex:
                    print(f"Error opening file: {ex}")

            # 1. Process Groups
            for key, g in state.hash_groups.items():
                # Filter valid files
                valid_items = [item for item in g if os.path.exists(item['path'])]
                if not valid_items: continue

                # Identify Best Shot if duplicates exist
                best_shot_path = None
                if len(valid_items) > 1:
                    # Pick best by quality score
                    best_item = max(valid_items, key=lambda x: x['quality']['overall'])
                    best_shot_path = best_item['path']
                
                for item in valid_items:
                     path = item['path']
                     fname = os.path.basename(path)
                     
                     is_duplicate = (len(valid_items) > 1)
                     is_best = (path == best_shot_path)
                     
                     file_type = item.get('type', 'image')
                     is_doc = item.get('is_doc', False)
                     is_pii = item.get('is_pii', False)
                     
                     dob = item.get('dob')
                     if dob:
                         date_path = os.path.join(dob.strftime("%Y"), dob.strftime("%m"))
                     else:
                         date_path = "Unknown"

                     # --- Categorization Logic ---
                     category = "Unknown"
                     
                     # 1. Trash (Duplicates) - HIGHEST PRIORITY
                     if is_duplicate and not is_best:
                         category = "Trash"
                         rel_target = os.path.join("Trash", fname)
                     
                     # 2. Custom / Learned Category (Few-Shot)
                     elif file_type == 'image' and (custom_cat := state.analyzer.find_custom_category(path)):
                         category = custom_cat
                         rel_target = os.path.join(custom_cat, date_path, fname)
                     
                     # 2. Personal PII (Priority over generic Docs)
                     elif is_pii:
                         category = "Personal"
                         rel_target = os.path.join("Personal", date_path, fname)
                     
                     # 3. Memes (Animated GIFs or Meme Content)
                     elif fname.lower().endswith('.gif') or (item.get('is_meme_visual', False) and not item.get('is_screenshot', False) and not item.get('is_doc', False)):
                         category = "Memes"
                         rel_target = os.path.join("Memes", date_path, fname)

                     # 4. Screenshots
                     elif item.get('is_screenshot', False):
                         category = "Screenshots"
                         rel_target = os.path.join("Screenshots", date_path, fname)

                     # 5. WhatsApp / Forwards (EXIF-based + Visual + Filename)
                     elif item.get('is_fwd', False) or ("-WA" in fname) or (item.get('is_forward_visual', False) and not item.get('is_screenshot', False)):
                         category = "Forwards"
                         rel_target = os.path.join("Forwards", date_path, fname)
                     
                     # 5. File Types
                     elif file_type == "video":
                         category = "Videos"
                         rel_target = os.path.join("Videos", date_path, fname)
                     elif file_type == "audio":
                         category = "Audios"
                         rel_target = os.path.join("Audios", fname)
                     elif file_type == "document":
                         category = "Documents"
                         rel_target = os.path.join("Documents", date_path, fname)
                     
                     # 7. Image Documents (CLIP)
                     elif is_doc:
                         category = "Documents"
                         rel_target = os.path.join("Documents", date_path, fname)

                     # 8. Fallback / Other
                     elif file_type == "other":
                         category = "Other Files"
                         rel_target = os.path.join("Other Files", fname)
                         
                     # 9. Standard Images (Final Else)
                     else:
                         category = "Images"
                         rel_target = os.path.join("Images", date_path, fname)
                    
                     # Save decision to item for actual processing
                     item['category'] = category
                     item['dest'] = rel_target
                     item['rel_target'] = rel_target
                     
                     try:
                         stats = os.stat(path)
                         size_raw = stats.st_size
                         size_kb = size_raw / 1024
                         dt_c = datetime.datetime.fromtimestamp(stats.st_ctime)
                         dt_m = datetime.datetime.fromtimestamp(stats.st_mtime)
                         dt_c_str = dt_c.strftime('%Y-%m-%d %H:%M')
                         dt_m_str = dt_m.strftime('%Y-%m-%d %H:%M')
                     except Exception: 
                         size_raw = 0
                         size_kb = 0
                         dt_c_str = "?"
                         dt_m_str = "?"
                         dt_c = datetime.datetime.min
                         dt_m = datetime.datetime.min
                     
                     # Get AI tags
                     tags = item.get('tags', [])
                     tags_str = ", ".join(tags[:3]) if tags else "N/A"
                     
                     # Extract folder name (parent directory)
                     folder_name = os.path.basename(os.path.dirname(path))
                     
                     all_files.append({
                         "name": fname,
                         "src": path,
                         "folder": folder_name,
                         "size_str": f"{size_kb:.1f} KB",
                         "size_raw": size_raw,
                         "created": dt_c_str,
                         "modified": dt_m_str,
                         "created_dt": dt_c,
                         "modified_dt": dt_m,
                         "dest": rel_target,
                         "category": category,
                         "tags": tags,
                         "tags_str": tags_str
                     })

            # Initial Load (Sort by Category default)
            all_files.sort(key=lambda x: x['category']) 

            # --- TOP HEADER FOR ORGANIZE TAB ---
            has_files = len(all_files) > 0
            
            btn_org = ft.ElevatedButton(
                "Organize Photos", 
                icon=ft.Icons.FOLDER, 
                on_click=run_organize, 
                visible=has_files,
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE
            )
            
            # Header Row (Status + Title + Button in single row)
            header_row = ft.Row([
                status_txt,
                ft.VerticalDivider(width=20),
                ft.Text(f"Preview ({len(all_files)} items)", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),  # Spacer
                btn_org
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            
            col_organize.controls.append(header_row)
            col_organize.controls.append(ft.Divider())

            # --- PREVIEW AND TABLE SETUP ---
            img_preview = ft.Image(src="", fit=ft.ImageFit.CONTAIN, visible=False, expand=True)
            txt_preview_hint = ft.Text("Click image to open", italic=True, size=12, color=ft.Colors.GREY_500)
            
            # Details Controls (Label + Value pairs)
            val_detail_source = ft.Text("", size=11, selectable=True)
            val_detail_dest = ft.Text("", size=11, selectable=True)
            val_detail_props = ft.Text("", size=11)
            val_detail_tags = ft.Text("", size=11, selectable=True)
            
            def open_preview_file(e):
                if img_preview.src:
                    try: os.startfile(img_preview.src)
                    except Exception: pass

            preview_inner_col = ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("Preview", weight=ft.FontWeight.BOLD),
                        txt_preview_hint
                    ], alignment=ft.MainAxisAlignment.START, spacing=15),
                    ft.Container(
                        content=img_preview,
                        on_click=open_preview_file,
                        alignment=ft.alignment.center,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=5,
                        padding=10,
                        expand=True, # Allow image to fill container
                        height=400   # Still keep fixed height for container constraint
                    ),
                    ft.Divider(),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Source:", weight=ft.FontWeight.BOLD, size=11),
                            val_detail_source,
                            ft.Container(height=5), # Spacer
                            ft.Text("Destination:", weight=ft.FontWeight.BOLD, size=11),
                            val_detail_dest,
                            ft.Container(height=5),
                            ft.Text("Properties:", weight=ft.FontWeight.BOLD, size=11),
                            val_detail_props,
                            ft.Container(height=5),
                            ft.Text("AI Tags:", weight=ft.FontWeight.BOLD, size=11),
                            val_detail_tags
                        ], spacing=0, alignment=ft.MainAxisAlignment.START),
                        alignment=ft.alignment.top_left,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True
            )

            preview_container = ft.Container(
                content=preview_inner_col,
                alignment=ft.alignment.top_left,
                width=500,
            )

            # --- TEACH MODE UI ---
            # --- TEACH MODE UI ---
            dd_reclassify = ft.Dropdown(
                hint_text="Correct Category",
                width=300, # Increased width
                options=[
                    ft.dropdown.Option("Documents"),
                    ft.dropdown.Option("Forwards"),
                    ft.dropdown.Option("Screenshots"),
                    ft.dropdown.Option("Memes"),
                    ft.dropdown.Option("Personal"),
                    ft.dropdown.Option("Images"),
                ],
                dense=True,
                text_size=12,
                content_padding=2,
            )
            
            def teach_and_move(e):
                if not img_preview.src:
                    page.open(ft.SnackBar(ft.Text("Select an image first.")))
                    return
                if not dd_reclassify.value:
                    page.open(ft.SnackBar(ft.Text("Select a correct category.")))
                    return
                
                path = img_preview.src
                new_cat = dd_reclassify.value
                
                # 1. Teach
                page.open(ft.SnackBar(ft.Text(f"Learning that this is a {new_cat}...")))
                page.update()
                
                success = state.analyzer.save_reference(path, new_cat)
                
                if success:
                     page.open(ft.SnackBar(ft.Text(f"Learned! Future similar images will be {new_cat}.")))
                     
                     # 2. IMMEDIATE UPDATE: Reflect change in UI
                     if state.selected_row:
                         # Update Row Cells
                         # Cell 0 = Category, Cell 7 = Destination
                         cell_cat = state.selected_row.cells[0].content
                         cell_dest = state.selected_row.cells[7].content
                         
                         cell_cat.value = new_cat
                         cell_dest.value = new_cat # Usually same as category
                         
                         # Update underlying data
                         state.selected_row.data['category'] = new_cat
                         state.selected_row.data['dest'] = new_cat
                         
                         # Refresh details pane - Use absolute path
                         full_dest = os.path.join(state.dest_dir, new_cat)
                         val_detail_dest.value = full_dest
                         
                         # Update the table cell for consistency (showing full path if preferred)
                         # However, user said "folder is not showing full path", so I will show FULL path in table too
                         cell_dest.value = full_dest
                         
                         state.selected_row.update()
                         page.update()
                else:
                    page.open(ft.SnackBar(ft.Text("Error learning.")))

            btn_teach = ft.ElevatedButton("Teach & Correct", on_click=teach_and_move, height=30)
            
            preview_inner_col.controls.append(ft.Divider())
            preview_inner_col.controls.append(ft.Row([dd_reclassify, btn_teach], alignment=ft.MainAxisAlignment.START))


            # --- TABLE LOGIC ---
            _col_hdr = lambda t: ft.Text(t, weight=ft.FontWeight.W_600, size=12, color="#A0A8C0")
            organize_table = ft.DataTable(
                columns=[
                    ft.DataColumn(_col_hdr("Category"), on_sort=lambda e: sort_data(e, 6)),
                    ft.DataColumn(_col_hdr("File"), on_sort=lambda e: sort_data(e, 0)),
                    ft.DataColumn(_col_hdr("Size"), on_sort=lambda e: sort_data(e, 1), numeric=True),
                    ft.DataColumn(_col_hdr("Created"), on_sort=lambda e: sort_data(e, 2)),
                    ft.DataColumn(_col_hdr("Modified"), on_sort=lambda e: sort_data(e, 3)),
                    ft.DataColumn(_col_hdr("AI Tags"), on_sort=lambda e: sort_data(e, 5)),
                    ft.DataColumn(_col_hdr("Source"), on_sort=lambda e: sort_data(e, 7)),
                    ft.DataColumn(_col_hdr("Destination"), on_sort=lambda e: sort_data(e, 4)),
                ],
                heading_row_height=44,
                heading_row_color="#1A1D27",
                data_row_min_height=40,
                data_row_max_height=40,
                column_spacing=16,
                border=ft.border.all(1, "#2D3244"),
                divider_thickness=0.5,
                sort_column_index=0,
                sort_ascending=True,
                show_checkbox_column=False
            )

            def on_row_select(e):
                selected_row = e.control
                src_path = selected_row.data['src']
                file_data = selected_row.data
                
                for row in organize_table.rows:
                    if row != selected_row: row.selected = False
                selected_row.selected = e.data == "true"
                
                # Update State
                if selected_row.selected:
                    state.selected_row = selected_row
                else:
                    state.selected_row = None
                
                if selected_row.selected:
                    # Update preview
                    # Use shared helper to support HEIC
                    src_p, src_b64 = get_display_src(src_path)
                    
                    ext = os.path.splitext(src_path)[1].lower()
                    img_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic', '.heif'}
                    vid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

                    if ext in img_exts:
                        img_preview.src = src_p if src_p else ""
                        img_preview.src_base64 = src_b64
                        img_preview.visible = True
                        txt_preview_hint.value = "Click image to open"
                    elif ext in vid_exts:
                        b64 = get_video_thumbnail(src_path)
                        if b64:
                            img_preview.src = ""
                            img_preview.src_base64 = b64
                            img_preview.visible = True
                            txt_preview_hint.value = "VIDEO - Click to open"
                        else:
                            img_preview.visible = False
                            txt_preview_hint.value = "Video preview unavailable"
                    else:
                        img_preview.visible = False
                        txt_preview_hint.value = "No preview available"
                    
                    # Update detail pane
                    val_detail_source.value = f"{file_data['src']}"
                    val_detail_dest.value = f"{os.path.join(state.dest_dir, file_data['dest'])}"
                    val_detail_props.value = f"Size: {file_data['size_str']} | Created: {file_data['created']} | Modified: {file_data['modified']}"
                    tags_full = ", ".join(file_data.get('tags', [])) if file_data.get('tags') else "N/A"
                    val_detail_tags.value = f"{tags_full}"
                else:
                    img_preview.visible = False
                    txt_preview_hint.value = "Select a file to preview"
                    val_detail_source.value = ""
                    val_detail_dest.value = ""
                    val_detail_props.value = ""
                    val_detail_tags.value = ""
                
                organize_table.update()
                preview_container.update()

            def create_rows(data_list):
                rows = []
                for f in data_list:
                    if state.current_theme == "Iron Man":
                        cat_color = "#FFD700"
                    elif state.current_theme == "Dark":
                        cat_color = "#7C6FF7"
                    else:
                        cat_color = "#4F46E5"
                    if f['category'] == 'Trash': cat_color = ft.Colors.RED
                    elif f['category'] == 'Other Files': cat_color = ft.Colors.ORANGE
                    elif f['category'] == 'Images': cat_color = ft.Colors.GREEN
                    elif f['category'] == 'Personal': cat_color = "#00FFFF" if state.current_theme == "Iron Man" else ft.Colors.CYAN
                    elif f['category'] == 'Memes': cat_color = ft.Colors.PINK
                    elif f['category'] == 'Forwards': cat_color = ft.Colors.PURPLE
                    elif f['category'] == 'Screenshots': cat_color = ft.Colors.AMBER
                    elif f['category'] in ['Videos', 'Documents', 'Audios']: cat_color = ft.Colors.BLUE_400

                    # Category badge chip
                    cat_badge = ft.Container(
                        ft.Text(f['category'], color=cat_color, size=11, weight=ft.FontWeight.W_600),
                        padding=ft.padding.symmetric(vertical=3, horizontal=10),
                        border_radius=20,
                        border=ft.border.all(1, cat_color),
                    )
                    rows.append(ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Container(cat_badge, width=120)),
                            ft.DataCell(ft.Container(ft.Text(f['name'], size=13, weight=ft.FontWeight.W_500, overflow=ft.TextOverflow.ELLIPSIS), width=200)),
                            ft.DataCell(ft.Container(ft.Text(f['size_str'], size=12, color="#A0A8C0"), width=80)),
                            ft.DataCell(ft.Container(ft.Text(f['created'], size=11, color="#A0A8C0"), width=120)),
                            ft.DataCell(ft.Container(ft.Text(f['modified'], size=11, color="#A0A8C0"), width=120)),
                            ft.DataCell(ft.Container(ft.Text(f['tags_str'], size=11, overflow=ft.TextOverflow.ELLIPSIS, color="#7C6FF7"), width=150)),
                            ft.DataCell(ft.Container(ft.Text(f['folder'], size=11, overflow=ft.TextOverflow.ELLIPSIS, color="#6B7280"), width=150)),
                            ft.DataCell(ft.Container(ft.Text(os.path.join(state.dest_dir, f['dest']), size=11, color="#6B7280"), width=250)),
                        ],
                        data=f,
                        on_select_changed=on_row_select
                    ))
                return rows

            def sort_data(e, col_index):
                keys = {0: 'name', 1: 'size_raw', 2: 'created_dt', 3: 'modified_dt', 4: 'dest', 5: 'tags_str', 6: 'category', 7: 'folder'}
                key = keys.get(col_index, 'dest')
                is_ascending = e.ascending
                all_files.sort(key=lambda x: x[key], reverse=not is_ascending)
                organize_table.rows = create_rows(all_files)
                organize_table.sort_ascending = is_ascending
                organize_table.sort_column_index = col_index
                organize_table.update()

            # Initial Rows Sort
            all_files.sort(key=lambda x: x['category']) 
            organize_table.rows = create_rows(all_files)
            
            # --- KEYBOARD NAVIGATION HELPERS ---
            state.preview_index = -1 
            
            def update_preview_by_index(idx):
                if 0 <= idx < len(all_files):
                    state.preview_index = idx
                    for r in organize_table.rows: r.selected = False
                    organize_table.rows[idx].selected = True
                    item = all_files[idx]
                    path = item['src']
                    
                    # Use shared helper
                    src_p, src_b64 = get_display_src(path)
                    ext = os.path.splitext(path)[1].lower()
                    supported_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic', '.heif'}
                    
                    if ext in supported_exts:
                        img_preview.src = src_p if src_p else ""
                        img_preview.src_base64 = src_b64
                        img_preview.visible = True
                        txt_preview_hint.value = f"[{idx+1}/{len(all_files)}] Click to open"
                    else:
                        img_preview.visible = False
                        txt_preview_hint.value = "No preview available"
                    
                    # Update detail pane
                    txt_detail_source.value = f"Source: {item['src']}"
                    txt_detail_dest.value = f"Destination: {os.path.join(state.dest_dir, item['dest'])}"
                    txt_detail_props.value = f"Size: {item['size_str']} | Created: {item['created']} | Modified: {item['modified']}"
                    tags_full = ", ".join(item.get('tags', [])) if item.get('tags') else "N/A"
                    txt_detail_tags.value = f"AI Tags: {tags_full}"
                    
                    organize_table.update()
                    preview_container.update()

            def on_keyboard(e: ft.KeyboardEvent):
                if tabs.selected_index == 1: 
                    if e.key == "ArrowDown":
                        new_idx = min(state.preview_index + 1, len(all_files) - 1)
                        update_preview_by_index(new_idx)
                    elif e.key == "ArrowUp":
                        new_idx = max(state.preview_index - 1, 0)
                        update_preview_by_index(new_idx)

            page.on_keyboard_event = on_keyboard

            # Split layout
            table_container = ft.Column(
                [ft.Row([organize_table], scroll=ft.ScrollMode.ALWAYS)],
                scroll=ft.ScrollMode.ALWAYS,
                expand=True
            )

            split_view = ft.Row(
                controls=[
                    ft.Container(
                        content=table_container,
                        expand=True,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=5
                    ),
                    preview_container
                ],
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )
            
            col_organize.controls.append(ft.Container(content=split_view, expand=True))

            # if non_image_files:
            #      chk_move_others.label = f"Include {len(non_image_files)} non-image files?"
            #      col_organize.controls.insert(1, chk_move_others)
            
            # Simplified: Always show checkbox if there are any files? Or just remove advanced logic for now.
            # User didn't ask for this specific feature to be fixed, just the error.
            # I'll just comment it out to prevent crash.
                 
            


            # OLD Button Logic Removed (moved to top)
            # disabled = len(all_files) == 0
            # btn_org = ft.ElevatedButton("Organize Photos", icon=ft.Icons.FOLDER, on_click=run_organize, disabled=disabled)
            # col_organize.controls.append(btn_org)

        page.update()

    def refresh_help_tab():
        col_help.controls.clear()
        col_help.controls.append(
            ft.Column([
                ft.Text("How to use PhotoAI Pro", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Step 1: Select Folders", weight=ft.FontWeight.BOLD),
                ft.Text("Choose a 'Source Folder' containing photo and a 'Destination Folder' where you want them organized."),
                
                ft.Text("\nStep 2: Scan for Duplicates", weight=ft.FontWeight.BOLD),
                ft.Text("Click 'Scan Source' in the 'Find Duplicates' tab. The AI will look for duplicate images based on visual content and quality."),
                
                ft.Text("\nStep 3: Cleanup (Optional)", weight=ft.FontWeight.BOLD),
                ft.Text("Review detected duplicates. Select the ones you want to discard and click 'Delete Selected'."),
                
                ft.Text("\nStep 4: Organize", weight=ft.FontWeight.BOLD),
                ft.Text("Go to the 'Organize' tab. Review the planned categories (Personal, Forwards, Videos, etc.). Click 'Organize Photos' to MOVE them into their new homes."),
                
                ft.Text("\nStep 5: Teach Mode (New!)", weight=ft.FontWeight.BOLD),
                ft.Text("If JARVIS makes a mistake:\n1. Click the file in the preview list.\n2. In the 'Details' pane (bottom left), select the correct category.\n3. Click 'Teach & Correct'.\nJARVIS will remember this correction for all future scans."),

                ft.Divider(),
                ft.Text("Tips:", italic=True),
                ft.Text(" • You can change the interface theme in Settings."),
                ft.Text(" • Use Arrow Keys to navigate photos in the Organize preview."),
                ft.Text(" • The app works offline once models are loaded."),
            ], spacing=10)
        )
        page.update()

    def refresh_about_tab():
        col_about.controls.clear()
        col_about.controls.append(
            ft.Column([
                ft.Text("About PhotoAI Pro", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    ft.Image(src="/logo_ai.png", width=100, height=100),
                    ft.Column([
                        ft.Text("PhotoAI Pro", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text("Version 1.0.0"),
                        ft.Text("Built for Advanced Personal Photo Organization"),
                    ])
                ]),
                ft.Text("\nPhotoAI Pro is an AI-powered desktop application designed to help you regain control over your digital photo library. By leveraging state-of-the-art computer vision models (CLIP and BLIP), it can automatically identify duplicates, detect sensitive documents, and organize your files based on visual context and metadata."),
                
                ft.Text("\nKey Features:", weight=ft.FontWeight.BOLD),
                ft.Text(" • Visual Duplicate Detection: Finds similar images even if they have different filenames."),
                ft.Text(" • AI Categorization: Automatically identifies 'Personal' documents, 'Forwards', and 'Screenshots'."),
                ft.Text(" • Date-Based Organization: Beautifully sorts your standard photos by Year and Month."),
                ft.Text(" • Teach Mode (Few-Shot Learning): Correct mistakes and the AI learns your preferences instantly."),
                ft.Text(" • Privacy First: All processing happens locally on your machine. Your photos never leave your device."),
                
                ft.Divider(),
                ft.Text("© 2025 JARVIS Imaging Systems. All rights reserved.", size=12, italic=True),
            ], spacing=10)
        )
        page.update()


    def refresh_history_tab():
        col_history.controls.clear()
        history = state.history_manager.get_history()
        
        if not history:
            col_history.controls.append(ft.Text("No history yet.", italic=True))
        else:
            history_list = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
            for entry in history:
                log_file = entry.get('logfile')
                # Define helper to avoid lambda capture issues
                def make_open_log(lp):
                    return lambda _: os.startfile(lp) if lp else None

                history_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.HISTORY),
                        title=ft.Text(f"{entry['timestamp']} - {entry['action']}"),
                        subtitle=ft.Text(str(entry['details'])),
                        trailing=ft.IconButton(
                            ft.Icons.DESCRIPTION, 
                            tooltip="View Detailed Movement Log",
                            on_click=make_open_log(log_file),
                            visible=bool(log_file)
                        ) if log_file else None
                    )
                )
            col_history.controls.append(history_list)
        page.update()

    def on_tab_change(e):
        # Force update to fix scrollbar layout issues on tab switch
        page.update()

    # --- TABS ---
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        on_change=on_tab_change,
        unselected_label_color=ft.Colors.GREY_500,
        label_color="#7C6FF7",
        indicator_color="#7C6FF7",
        tabs=[
            ft.Tab(
                text="Find Duplicates",
                icon=ft.Icons.SEARCH,
                content=ft.Container(
                    content=col_find_dups,
                    padding=10
                ),
            ),
            ft.Tab(
                text="Organize",
                icon=ft.Icons.FOLDER_COPY,
                content=ft.Container(
                    content=col_organize,
                    padding=10
                )
            ),

            ft.Tab(
                text="History",
                icon=ft.Icons.HISTORY,
                content=ft.Container(
                    content=col_history,
                    padding=10
                )
            ),

            ft.Tab(
                text="Help",
                icon=ft.Icons.HELP_OUTLINE,
                content=ft.Container(
                    content=col_help,
                    padding=20
                )
            ),
            ft.Tab(
                text="About",
                icon=ft.Icons.INFO_OUTLINE,
                content=ft.Container(
                    content=col_about,
                    padding=20
                )
            ),
        ],
        expand=True,
    )

    # Apply initial theme now that all components are defined
    apply_theme(state.current_theme)

    page.add(tabs)
    
    # Load history, help, and about on start
    refresh_history_tab()
    refresh_help_tab()
    refresh_about_tab()
    page.update()
    
    # Close PyInstaller splash screen now that Flet window is visible
    # Don't wait for AI models - they load in background
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
