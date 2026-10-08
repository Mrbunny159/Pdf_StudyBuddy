# probe.py — checks every Flet API the project uses
import flet as ft

checks = {
    "ft.Image(src=...)":        lambda: ft.Image(src="aGVsbG8=", width=100, height=100),
    "ft.BoxFit.CONTAIN":        lambda: ft.BoxFit.CONTAIN,
    "ft.Colors.GREY_700":       lambda: ft.Colors.GREY_700,
    "ft.Icons.FILE_OPEN":       lambda: ft.Icons.FILE_OPEN,
    "ft.Icons.CHEVRON_LEFT":    lambda: ft.Icons.CHEVRON_LEFT,
    "ft.Icons.MENU_BOOK":       lambda: ft.Icons.MENU_BOOK,
    "ft.MainAxisAlignment.CENTER":  lambda: ft.MainAxisAlignment.CENTER,
    "ft.CrossAxisAlignment.CENTER": lambda: ft.CrossAxisAlignment.CENTER,
    "ft.ScrollMode.AUTO":       lambda: ft.ScrollMode.AUTO,
    "ft.ThemeMode.LIGHT":       lambda: ft.ThemeMode.LIGHT,
    "ft.FilePicker()":          lambda: ft.FilePicker(),
    "ft.FilePickerFileType.CUSTOM": lambda: ft.FilePickerFileType.CUSTOM,
    "ft.AppBar":                lambda: ft.AppBar(title=ft.Text("t")),
    "ft.IconButton":            lambda: ft.IconButton(ft.Icons.FILE_OPEN),
    "ft.SnackBar":              lambda: ft.SnackBar(ft.Text("x")),
    "ft.Column(scroll=...)":    lambda: ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True),
    "ft.Container(padding=10)": lambda: ft.Container(content=ft.Text("x"), padding=10),
    "ft.Row(alignment=...)":    lambda: ft.Row([], alignment=ft.MainAxisAlignment.CENTER),
}

print(f"Flet version: {getattr(ft, '__version__', 'unknown')}\n")
for name, fn in checks.items():
    try:
        fn()
        print(f"OK   {name}")
    except Exception as ex:
        print(f"FAIL {name}  ->  {type(ex).__name__}: {ex}")