import base64
import inspect
import webbrowser
import flet as ft
from pdf_core import PdfBook
import ai_client
import visuals_client

VIEW_WIDTH = 900
BOX_FIT_COVER = getattr(ft.BoxFit, "COVER", getattr(getattr(ft, "ImageFit", None), "COVER", "cover"))
BOX_FIT_CONTAIN = getattr(ft.BoxFit, "CONTAIN", getattr(getattr(ft, "ImageFit", None), "CONTAIN", "contain"))
Padding = getattr(ft, "Padding", ft.padding)
Border = getattr(ft, "Border", ft.border)


def main(page: ft.Page):
    page.title = "PDF Study Assistant"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1100
    page.window.height = 850

    state = {"book": None, "current": 0, "stream_id": 0,
             "tab": "explain", "summary_cache": {}, "summary_loading": None}

    # ==========================================
    # 1. DEFINE ALL FUNCTIONS FIRST
    # ==========================================

    async def generate_and_stream(word, context, my_stream_id):
        explanation_text.value = "Soch raha hoon..."
        page.update()
        try:
            async for chunk in ai_client.stream_explanation(word, context):
                if state.get("stream_id") != my_stream_id:
                    break
                explanation_text.value += chunk
                page.update()
        except Exception as e:
            if state.get("stream_id") == my_stream_id:
                explanation_text.value = f"Error: {e}"
                page.update()

    async def load_images(word, context, my_stream_id):
        images_row.controls.clear()
        images_row.controls.append(
            ft.Text("Finding relevant images...", size=11, color=ft.Colors.GREY_500, italic=True)
        )
        
        page.update()

        # 1. Ask AI for a smart, context-aware search query
        query = await ai_client.get_image_query(word, context)
        if state.get("stream_id") != my_stream_id:
            return

        # 2. Search (smart query first, plain word fallback handled inside)
        try:
            results = await visuals_client.search_images(query, word, limit=3)
        except Exception as ex:
            print(f"[visuals] load_images error: {ex}")
            results = []

        if state.get("stream_id") != my_stream_id:
            return

        caption_text.value = f'"{query}" - tap an image to open it full size'

        images_row.controls.clear()
        if not results:
            images_row.controls.append(
                ft.Text("No images found", size=11, color=ft.Colors.GREY_500, italic=True)
            )
        else:
            for thumb_b64, full_url in results:
                img = ft.Image(src=thumb_b64, width=80, height=80, fit=BOX_FIT_COVER)
                box = ft.GestureDetector(
                    content=ft.Container(
                        content=img,
                        border_radius=6,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        tooltip="Open full image",
                    ),
                    on_tap=lambda e, url=full_url: webbrowser.open(url),
                    mouse_cursor=ft.MouseCursor.CLICK,
                )
                images_row.controls.append(box)
        page.update()

    async def generate_summary(idx, page_text):
        summary_text.value = "Summary aa rahi hai..."
        page.update()
        collected = []
        try:
            async for chunk in ai_client.stream_summary(page_text):
                if state.get("summary_loading") != idx:
                    return
                collected.append(chunk)
                summary_text.value = "".join(collected)
                page.update()
            state["summary_cache"][idx] = "".join(collected)
        except Exception as e:
            summary_text.value = f"Error: {e}"
            page.update()
        finally:
            if state.get("summary_loading") == idx:
                state["summary_loading"] = None

    def ensure_summary():
        idx = state["current"]
        if idx in state["summary_cache"]:
            summary_text.value = state["summary_cache"][idx]
            page.update()
            return
        if state.get("summary_loading") is not None:
            return
        state["summary_loading"] = idx
        page_text = state["book"].doc[idx].get_text("text")
        page.run_task(generate_summary, idx, page_text)

    def switch_tab(name):
        state["tab"] = name
        for tab_ctl, view_ctl, key in (
            (tab_explain, explain_view, "explain"),
            (tab_summary, summary_view, "summary"),
            (tab_visualize, visualize_view, "visualize"),
        ):
            active = (key == name)
            view_ctl.visible = active
            tab_ctl.bgcolor = ft.Colors.BLUE_100 if active else ft.Colors.TRANSPARENT
            tab_ctl.content.color = ft.Colors.BLUE_700 if active else ft.Colors.GREY_600
        if name == "summary":
            ensure_summary()
        page.update()

    def hide_popover():
        highlight_box.visible = False
        popover.visible = False
        page.update()

    def on_page_tap(e):
        if not state["book"]:
            return

        page_doc = state["book"].doc[state["current"]]
        s = page_doc.rect.width / VIEW_WIDTH

        local_x = getattr(e, "local_x", None)
        local_y = getattr(e, "local_y", None)
        if local_x is None and hasattr(e, "local_position") and e.local_position:
            local_x = e.local_position.x
            local_y = e.local_position.y
        if local_x is None or local_y is None:
            return

        tap_x = local_x * s
        tap_y = local_y * s

        words = state["book"].words(state["current"])
        hit = None

        for w in words:
            x0, y0, x1, y1, text, *_ = w
            if (x0 - 2) <= tap_x <= (x1 + 2) and (y0 - 2) <= tap_y <= (y1 + 2):
                hit = w
                break

        if hit:
            x0, y0, x1, y1, text, *_ = hit

            highlight_box.left = x0 / s
            highlight_box.top = y0 / s
            highlight_box.width = (x1 - x0) / s
            highlight_box.height = (y1 - y0) / s
            highlight_box.visible = True

            selected_word_text.value = text
            explanation_text.value = ""

            pop_x = (x1 / s) + 15
            pop_y = y0 / s
            if pop_x + 280 > VIEW_WIDTH:
                pop_x = (x0 / s) - 280 - 15
            if pop_y < 0:
                pop_y = 5

            popover.left = pop_x
            popover.top = pop_y
            popover.visible = True

            state["stream_id"] += 1
            my_id = state["stream_id"]
            context = state["book"].get_context(state["current"], hit)

            switch_tab("explain")
            page.update()

            page.run_task(generate_and_stream, text, context, my_id)
            page.run_task(load_images, text, context, my_id)
        else:
            hide_popover()

    def show_page(index: int):
        pix = state["book"].get_pixmap(index)
        b64 = base64.b64encode(pix.tobytes("png")).decode()

        page_image.src = b64
        if hasattr(page_image, "src_base64"):
            page_image.src_base64 = b64
        page_image.width = VIEW_WIDTH
        page_image.height = VIEW_WIDTH * pix.height / pix.width

        status_text.value = f"Page {index + 1} of {state['book'].page_count}"
        state["summary_loading"] = None
        hide_popover()
        page.update()

    def go_prev(e):
        if state["book"] and state["current"] > 0:
            state["current"] -= 1
            show_page(state["current"])

    def go_next(e):
        if state["book"] and state["current"] < state["book"].page_count - 1:
            state["current"] += 1
            show_page(state["current"])

    def show_error(msg: str):
        sb = ft.SnackBar(ft.Text(msg))
        if hasattr(page, "show_dialog"):
            page.show_dialog(sb)
        elif hasattr(page, "open"):
            page.open(sb)
        elif hasattr(page, "snack_bar"):
            page.snack_bar = sb
            sb.open = True
            page.update()

    def load_pdf(path: str):
        try:
            state["book"] = PdfBook(path)
        except Exception as ex:
            show_error(f"Could not open PDF: {ex}")
            return
        state["current"] = 0
        hint.visible = False
        viewer.visible = True
        show_page(0)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e and e.files:
            load_pdf(e.files[0].path)

    async def open_pdf(e):
        try:
            res = picker.pick_files(
                dialog_title="Choose a PDF",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
            )
            if inspect.isawaitable(res):
                files = await res
                if files and files[0].path:
                    load_pdf(files[0].path)
        except Exception as ex:
            print(f"[open_pdf] pick_files error: {ex}")

    # ==========================================
    # 2. BUILD UI CONTROLS
    # ==========================================

    page_image = ft.Image(src="", width=VIEW_WIDTH, fit=BOX_FIT_CONTAIN)
    status_text = ft.Text("Open a PDF to get started", size=14, color=ft.Colors.GREY_700)

    highlight_box = ft.Container(
        bgcolor=ft.Colors.YELLOW_300,
        opacity=0.4,
        border_radius=2,
        visible=False,
    )

    selected_word_text = ft.Text("...", size=14, color=ft.Colors.BLUE_700, weight=ft.FontWeight.BOLD)
    explanation_text = ft.Text("Explanation will appear here...", size=12, color=ft.Colors.GREY_800, selectable=True)
    summary_text = ft.Text("", size=12, color=ft.Colors.GREY_800, selectable=True)
    images_row = ft.Row(spacing=6)
    caption_text = ft.Text("Tap an image to open it full size", size=10, color=ft.Colors.GREY_500)

    explain_view = ft.Column([explanation_text], tight=True, spacing=5, visible=True)
    summary_view = ft.Column([summary_text], tight=True, spacing=5, visible=False)
    visualize_view = ft.Column([images_row, caption_text], tight=True, spacing=5, visible=False)

    tab_explain = ft.Container(
        content=ft.Text("Explain", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
        padding=Padding.symmetric(horizontal=10, vertical=5),
        border_radius=6,
        bgcolor=ft.Colors.BLUE_100,
        on_click=lambda e: switch_tab("explain"),
    )
    tab_summary = ft.Container(
        content=ft.Text("Summary", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600),
        padding=Padding.symmetric(horizontal=10, vertical=5),
        border_radius=6,
        on_click=lambda e: switch_tab("summary"),
    )
    tab_visualize = ft.Container(
        content=ft.Text("Visualize", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600),
        padding=Padding.symmetric(horizontal=10, vertical=5),
        border_radius=6,
        on_click=lambda e: switch_tab("visualize"),
    )
    tabs_row = ft.Row([tab_explain, tab_summary, tab_visualize], spacing=4)

    popover = ft.Container(
        width=280,
        padding=10,
        border_radius=8,
        bgcolor=ft.Colors.WHITE,
        border=Border.all(1, ft.Colors.GREY_300),
        shadow=ft.BoxShadow(spread_radius=1, blur_radius=5, color="#33000000"),
        visible=False,
        content=ft.Column([
            ft.Row([
                ft.Text("Word:", size=14, weight=ft.FontWeight.BOLD),
                selected_word_text
            ], tight=True),
            ft.Divider(height=8),
            tabs_row,
            ft.Divider(height=8),
            explain_view,
            summary_view,
            visualize_view,
            ft.Row([
                ft.IconButton(ft.Icons.CLOSE, icon_size=16, tooltip="Close", on_click=lambda e: hide_popover()),
            ], alignment=ft.MainAxisAlignment.END, tight=True)
        ], tight=True, spacing=5)
    )

    inner_stack = ft.Stack([page_image, highlight_box], width=VIEW_WIDTH)
    page_gesture = ft.GestureDetector(
        content=inner_stack,
        on_tap_down=on_page_tap,
        mouse_cursor=ft.MouseCursor.TEXT,
    )
    outer_stack = ft.Stack([page_gesture, popover], width=VIEW_WIDTH)

    picker = ft.FilePicker(on_result=on_file_picked)
    if hasattr(page, "services"):
        page.services.append(picker)
    if hasattr(page, "overlay"):
        page.overlay.append(picker)

    hint = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.MENU_BOOK, size=64, color=ft.Colors.GREY_400),
            ft.Text("Click 📂 (top-right) to open a PDF", size=18, color=ft.Colors.GREY_500),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        expand=True,
    )

    viewer = ft.Column([
        ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Previous page", on_click=go_prev),
            status_text,
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Next page", on_click=go_next),
        ], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(
            ft.Row([outer_stack], alignment=ft.MainAxisAlignment.CENTER),
            padding=10,
        ),
    ], scroll=ft.ScrollMode.AUTO, expand=True, visible=False)

    if hasattr(ft, "PickFiles"):
        open_button = ft.IconButton(
            ft.Icons.FILE_OPEN,
            tooltip="Open PDF",
            action=ft.PickFiles(
                file_picker=picker,
                dialog_title="Choose a PDF",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
            ),
        )
    else:
        open_button = ft.IconButton(
            ft.Icons.FILE_OPEN,
            tooltip="Open PDF",
            on_click=open_pdf,
        )

    page.appbar = ft.AppBar(
        title=ft.Text("PDF Study Assistant"),
        actions=[open_button],
    )

    page.add(ft.Column([hint, viewer], expand=True))


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)