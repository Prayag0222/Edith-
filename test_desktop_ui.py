import time
import webview

from app.ui.desktop_window import EdithDesktopWindow


desktop = EdithDesktopWindow()

desktop.create()


def test_ui():

    print("EDITH UI test started.")

    time.sleep(2)

    desktop.show()

    states = [
        "LISTENING",
        "THINKING",
        "SPEAKING",
        "READY",
    ]

    for state in states:

        print(f"Testing state: {state}")

        desktop.set_state(state)

        time.sleep(3)

    desktop.hide()

    print("Popup hidden.")

    time.sleep(3)

    desktop.close()


webview.start(test_ui)