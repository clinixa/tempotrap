import win32gui
import win32con
import win32api
import win32process
import subprocess
import psutil
import os
import time
import sys
import pyautogui
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
import time
import keyboard
import os
from pynput.keyboard import Controller as KeyboardController
import logging
import ctypes
from ctypes import wintypes
import requests
from datetime import datetime
import random
# Windows API setup
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]


user32 = ctypes.WinDLL('user32', use_last_error=True)


class Locator:
    def __init__(self, root):
        self.root = root
        self.root.title("Sage")
        self.root.geometry("600x500")
        self.target_window = None
        self.window_title = None
        self.last_click_time = time.time()
        self.click_timeout = 1200  #20 minutes timeout
        # Configure settings
        pyautogui.FAILSAFE = True
        self.template_folder = os.path.join(os.path.expanduser("~"), "Desktop", "Sage")
        self.current_position = (-5, -23)

        # Initialize state
        self.image_paths = []
        self.is_searching = False
        self.keyboard_controller = KeyboardController()
        # Test webhook on startup
        webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"
        data = {
            "content": "<@everyone> ```Script initialized```"
        }
        requests.post(webhook_url, json=data)
        # Movement directions
        self.directions = {
            "_": (0, -1),  # Up
            "é": (0, 1),  # Down
            "'": (-1, 0),  # Left
            "-": (1, 0)  # Right
        }

        # Grid path definition
        self.path = [
            (-5, -23), (-4, -23), (-4, -24), (-3, -24), (-3, -23), (-2, -23), (-2, -24), (-1, -24),
            (0, -24), (1, -24), (1, -25), (1, -26), (0, -26), (0, -27), (-1, -27), (-2, -27),
            (-2, -28), (-3, -28), (-4, -28), (-5, -28), (-6, -28), (-6, -27), (-6, -26), (-6, -25),
            (-5, -25), (-5, -24), (-5, -23)
        ]

        # Path from Zaap to starting point

        #self.zaap_to_start = [
            #(-31, -56), (-30, -56), (-29, -56), (-28, -56), (-78, -45), (-77, -45),
            #(-76, -45), (-76, -46), (-76, -47), (-75, -47), (-75, -48), (-24, -55)
        #]
        # Positions of Zaap, Bank, and HDV
        self.ZAAP_LOCATION = (-31, -56)
        self.BANK_LOCATION = (-31, -57)
        self.HDV_LOCATION = (-30, -54)

        self.setup_ui()
        self.load_images_from_folder()
        self.mode = 'hdv'  # Default mode
        # Setup hotkeys
        keyboard.add_hotkey('F3', lambda: self.toggle_search_hotkey('hdv'))
        keyboard.add_hotkey('F4', lambda: self.toggle_search_hotkey('bank'))
        keyboard.add_hotkey('esc', self.emergency_stop)
        # Add new hotkey for manual heavy status trigger
        keyboard.add_hotkey('²', self.trigger_heavy_status)

    def trigger_heavy_status(self):
        """Manually trigger the heavy status bank sequence"""
        self.log_result("Manual heavy status trigger activated")
        # Temporarily store search state
        temp_searching = self.is_searching
        self.is_searching = False

        # Start a new thread to handle the bank sequence
        threading.Thread(target=lambda: self.handle_combat(), daemon=True).start()

        # Restore search state in case handle_combat fails
        self.is_searching = temp_searching
    def find_dofus_window(self):
        """Find the Dofus window with 'Release' in the title."""

        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if 'Release' in title:
                    windows.append((hwnd, title))
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows[0] if windows else (None, None)

    def focus_dofus_window(self):
        """Focus the Dofus window."""
        hwnd, title = self.find_dofus_window()
        if hwnd:
            self.target_window = hwnd
            self.window_title = title
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Bring to front and focus
            win32gui.SetForegroundWindow(hwnd)
            return True
        return False

    def restart_dofus(self):
        """Close Dofus and restart it."""
        try:
            # Kill Dofus process
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == 'Dofus.exe':
                    proc.kill()

            time.sleep(10)  # Wait for process to close

            # Start Dofus using desktop shortcut
            shortcut_path = os.path.join(os.path.expanduser("~"), "Desktop", "Dofus.lnk")
            subprocess.Popen(["cmd", "/c", "start", "", shortcut_path])

            # Wait 50 seconds
            time.sleep(50)

            # Focus window
            if self.focus_dofus_window():
                # Spam 'à' for 5 seconds
                start_time = time.time()
                while time.time() - start_time < 5:
                    self.keyboard_controller.press('à')
                    time.sleep(0.1)
                    self.keyboard_controller.release('à')
                    time.sleep(0.2)  # Small delay between presses

                # Reset position to start of path
                self.current_position = self.path[0]
                self.log_result("Position reset to start after restart")

                # Restart search
                self.is_searching = True
                threading.Thread(target=self.search_loop, daemon=True).start()
                self.start_screenshot_monitor()

        except Exception as e:
            self.log_result(f"Error restarting Dofus: {str(e)}")

    def check_shit_image(self):
        """Check for the shit.png image."""
        shit_image_path = r"C:\Users\umbra\Desktop\Sage\shit.png"
        try:
            location = pyautogui.locateOnScreen(
                shit_image_path,
                confidence=0.6,
                grayscale=False
            )
            return location is not None
        except Exception:
            return False

    def check_and_handle_click(self):
        """Check for click.png and handle clicking until clack.png appears"""
        click_image_path = os.path.join(self.template_folder, "click.png")
        clack_image_path = os.path.join(self.template_folder, "clack.png")

        try:
            click_location = pyautogui.locateOnScreen(
                click_image_path,
                confidence=0.9,
                grayscale=False
            )

            if click_location:
                # Found click.png - only log when we start the sequence
                self.log_result("Found click.png - starting click sequence")
                temp_searching = self.is_searching
                self.is_searching = False

                x, y = pyautogui.center(click_location)

                # Setup mouse click inputs
                input_down = INPUT()
                input_up = INPUT()
                input_down.type = INPUT_MOUSE
                input_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
                input_up.type = INPUT_MOUSE
                input_up.mi.dwFlags = MOUSEEVENTF_LEFTUP

                # Click until clack.png appears or maximum attempts reached
                max_attempts = 3
                attempts = 0
                clicking = True

                while clicking and attempts < max_attempts:
                    attempts += 1
                    # Click actions without logging
                    pyautogui.moveTo(x, y, duration=0.2)
                    user32.SendInput(1, ctypes.byref(input_down), ctypes.sizeof(INPUT))
                    time.sleep(0.1)
                    user32.SendInput(1, ctypes.byref(input_up), ctypes.sizeof(INPUT))
                    time.sleep(1)

                    # Check for clack.png silently
                    try:
                        if pyautogui.locateOnScreen(clack_image_path, confidence=0.9, grayscale=False):
                            self.log_result("Found clack.png - sequence complete")
                            clicking = False
                    except:
                        pass

                # Move mouse to center without logging
                screen_width, screen_height = pyautogui.size()
                center_x = screen_width // 2
                center_y = screen_height // 2
                pyautogui.moveTo(center_x, center_y, duration=0.2)

                # Resume normal operation silently
                self.is_searching = temp_searching
                return True

            return False

        except:
            if 'temp_searching' in locals():
                self.is_searching = temp_searching
            return False
    def setup_ui(self):
        # Create main frame and widgets
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Info header
        info_frame = ttk.Frame(self.main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(info_frame, text="F3: Start/Stop  |  ESC: Emergency Stop  |  Start: [-5, -23]",
                  font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        self.template_count = tk.StringVar(value="Images: 0/200")
        ttk.Label(info_frame, textvariable=self.template_count).pack(side=tk.RIGHT)

        # Controls
        ttk.Button(self.main_frame, text="Reload Images",
                   command=self.load_images_from_folder).pack(pady=5)

        self.preview_label = ttk.Label(self.main_frame)
        self.preview_label.pack(pady=10)
        self.preview_label.pack(pady=10)

        self.status_var = tk.StringVar(value="Ready (Full Screen Scan)")
        ttk.Label(self.main_frame, textvariable=self.status_var).pack(pady=5)

        self.search_btn = ttk.Button(self.main_frame, text="Start Search (F3)",
                                     command=self.toggle_search)
        self.search_btn.pack(pady=5)

        # Results log
        self.results_text = tk.Text(self.main_frame, height=10, width=50)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)
        scrollbar = ttk.Scrollbar(self.main_frame, command=self.results_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.config(yscrollcommand=scrollbar.set)

    def load_images_from_folder(self):
        try:
            if not os.path.exists(self.template_folder):
                os.makedirs(self.template_folder)
                self.log_result(f"Created folder: {self.template_folder}")
                return

            self.image_paths = [
                                   os.path.join(self.template_folder, f)
                                   for f in os.listdir(self.template_folder)
                                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))
                               ][:200]

            self.template_count.set(f"Images: {len(self.image_paths)}/200")
            self.log_result(f"Loaded {len(self.image_paths)} images")

            if self.image_paths:
                self.load_preview(self.image_paths[0])

        except Exception as e:
            self.log_result(f"Error loading images: {str(e)}")

    def load_preview(self, image_path):
        try:
            image = Image.open(image_path)
            image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=photo)
            self.preview_label.image = photo
            self.status_var.set(f"Current: {os.path.basename(image_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")

    def get_next_move(self, current, target):
        dx = target[0] - current[0]
        dy = target[1] - current[1]
        if dx > 0: return "-"  # Right
        if dx < 0: return "'"  # Left
        if dy > 0: return "é"  # Down
        if dy < 0: return "_"  # Up
        return None

    def execute_move(self, direction_key):
        self.keyboard_controller.press(direction_key)
        time.sleep(0.1)
        self.keyboard_controller.release(direction_key)
        time.sleep(0.5)

        dx, dy = self.directions[direction_key]
        self.current_position = (
            self.current_position[0] + dx,
            self.current_position[1] + dy
        )
        self.log_result(f"Moving to: {self.current_position}")

    def navigate_to_position(self, target):
        while self.current_position != target and self.is_searching:
            next_move = self.get_next_move(self.current_position, target)
            if next_move:
                self.execute_move(next_move)
            else:
                break

    def get_next_position(self):
        try:
            current_index = self.path.index(self.current_position)
            next_index = (current_index + 1) % len(self.path)
            return self.path[next_index]
        except ValueError:
            return self.path[0]

    def check_and_click_image(self, image_path):
        try:
            if "Abandon.png" in image_path:
                location = pyautogui.locateOnScreen(
                    image_path,
                    confidence=0.6,
                    grayscale=True
                )
            if "close.png" in image_path:
                location = pyautogui.locateOnScreen(
                    image_path,
                    confidence=0.6,
                    grayscale=True
                )
            else:
                location = pyautogui.locateOnScreen(
                    image_path,
                    confidence=0.9,
                    grayscale=False
                )

            if location:
                x, y = pyautogui.center(location)
                pyautogui.moveTo(x, y, duration=0.2)

                input_down = INPUT()
                input_up = INPUT()

                input_down.type = INPUT_MOUSE
                input_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
                input_up.type = INPUT_MOUSE
                input_up.mi.dwFlags = MOUSEEVENTF_LEFTUP

                user32.SendInput(1, ctypes.byref(input_down), ctypes.sizeof(INPUT))
                time.sleep(0.1)
                user32.SendInput(1, ctypes.byref(input_up), ctypes.sizeof(INPUT))

                self.log_result(f"Clicked image at: ({x}, {y})")
                self.last_click_time = time.time()  # Add this line to update last click time
                return True

        except Exception as e:
            self.log_result(f"Click error: {str(e)}")
        return False

    def check_click_timeout(self):
        """Check if we haven't clicked anything for a while and trigger zaap reset if needed"""
        current_time = time.time()
        if current_time - self.last_click_time > self.click_timeout:
            self.log_result("No clicks detected for 20 minutes - triggering zaap reset")
            # Press 'à' key to trigger zaap
            self.keyboard_controller.press('à')
            time.sleep(0.1)
            self.keyboard_controller.release('à')
            time.sleep(2)  # Wait for zaap screen

            zaap_path = os.path.join(self.template_folder, "Zaap.png")
            if os.path.exists(zaap_path) and self.check_and_click_image(zaap_path):
                pyautogui.doubleClick(915, 930)
                pyautogui.click(915, 930)
                pyautogui.doubleClick(915, 930)
                pyautogui.click(915, 930)
                pyautogui.doubleClick(915, 930)
                pyautogui.click(915, 930)
                time.sleep(1)
                self.log_result("Zaap found - resetting to start position")
                self.current_position = self.path[0]
            return True
            return True
        return False
    def navigate_to_position_with_delay(self, target, delay=10):
        """Navigate to a position with a specified delay between grid movements."""
        while self.current_position != target and self.is_searching:
            next_move = self.get_next_move(self.current_position, target)
            if next_move:
                self.execute_move(next_move)
                time.sleep(delay)  # 16-second delay between grid movements
            else:
                break

    #HDV function here, similar to a macro

    def check_hdv_sell_button(self):
        """Check for both variants of the HDV sell button and click multiple times if found."""
        hdv_sell_button_path = os.path.join(self.template_folder, "hdv-sell-button.png")
        hdv_sell_button_lit_path = os.path.join(self.template_folder, "hdv-sell-button-lit.png")

        # Try to find either button variant
        location = None
        for button_path in [hdv_sell_button_lit_path, hdv_sell_button_path]:
            try:
                location = pyautogui.locateOnScreen(button_path, confidence=0.9, grayscale=False)
                if location:
                    break
            except Exception:
                continue

        if location:
            x, y = pyautogui.center(location)
            pyautogui.moveTo(x, y, duration=0.2)

            # Create input structures for mouse clicks
            input_down = INPUT()
            input_up = INPUT()
            input_down.type = INPUT_MOUSE
            input_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
            input_up.type = INPUT_MOUSE
            input_up.mi.dwFlags = MOUSEEVENTF_LEFTUP

            # Click 30 times with 0.2s delay
            for _ in range(30):
                if not self.is_searching:  # Stop if search is cancelled
                    break
                user32.SendInput(1, ctypes.byref(input_down), ctypes.sizeof(INPUT))
                time.sleep(0.1)
                user32.SendInput(1, ctypes.byref(input_up), ctypes.sizeof(INPUT))
                time.sleep(0.2)

            self.log_result(f"Clicked sell button 30 times at: ({x}, {y})")
            return True

        return False

    def handle_hdv_selling(self):
        """Handle the House of Trade (HDV) selling process."""
        try:
            # Navigate to Bonta HDV
            self.log_result("Navigating to Bonta HDV")

            # Click Bonta HDV
            bonta_hdv_path = os.path.join(self.template_folder, "Bonta-hdv.png")
            if self.check_and_click_image(bonta_hdv_path):
                time.sleep(4)  # Wait 10 seconds after clicking

                # Click HDV Sell Section
                hdv_sell_section_path = os.path.join(self.template_folder, "hdv-sell-section.png")
                if self.check_and_click_image(hdv_sell_section_path):
                    time.sleep(4)

                    # Sell Sage
                    Sage_inv_path = os.path.join(self.template_folder, "Sage-inv.png")
                    if self.check_and_click_image(Sage_inv_path):
                        time.sleep(6)  # Wait after clicking Sage
                        hdv_deal_path = os.path.join(self.template_folder, "hdv-deal.png")
                        if self.check_and_click_image(hdv_deal_path):
                            time.sleep(6)  # Wait after clicking deal
                            # Click price input and type 3200
                            pyautogui.click(x=443, y=355)
                            time.sleep(6)  # Wait before typing price
                            pyautogui.typewrite("25000")
                            time.sleep(6)  # Wait after typing price

                            # Verify price and spam sell button
                            Sage_hdv_price_path = os.path.join(self.template_folder, "Sage-hdv-price.png")
                            if os.path.exists(Sage_hdv_price_path):
                                self.log_result("Sage price confirmed")

                                # Spam sell button
                                hdv_sell_button_path = os.path.join(self.template_folder, "hdv-sell-button.png")
                                for _ in range(40):
                                    self.check_and_click_image(hdv_sell_button_path)
                                    time.sleep(0.3)
                                time.sleep(2.5)

                            # Check for no deal
                            hdv_no_deal_path = os.path.join(self.template_folder, "hdv-no-deal.png")
                            if os.path.exists(hdv_no_deal_path):
                                self.log_result("No deal for Sage")
                    # Leave HDV
                    hdv_leave_path = os.path.join(self.template_folder, "hdv-leave.png")
                    if self.check_and_click_image(hdv_leave_path):
                        # Navigate back to starting position
                        time.sleep(1)
                        self.navigate_to_position_with_delay((-30, -54), delay=10)
                        self.navigate_to_position_with_delay((-5, -25))
                        return True

        except Exception as e:
            self.log_result(f"HDV selling error: {str(e)}")

        return False

    def deposit_Sage_and_restart(self):
        """Handle the Sage deposit process and restart sequence."""
        try:
            # Find and CTRL+click Sage with specific region
            Sage_path = os.path.join(self.template_folder, "Sage-inv.png")
            location = pyautogui.locateOnScreen(
                Sage_path,
                confidence=0.9,
                region=(833, 163, 1246 - 833, 898 - 163),
                grayscale=False
            )

            if location:
                x, y = pyautogui.center(location)
                # Hold CTRL and click
                keyboard.press('ctrl')
                pyautogui.click(x, y)
                keyboard.release('ctrl')
                time.sleep(1)

                # Click actions.png with same region
                actions_path = os.path.join(self.template_folder, "actions.png")
                actions_location = pyautogui.locateOnScreen(
                    actions_path,
                    confidence=0.9,
                    region=(833, 163, 1246 - 833, 898 - 163),
                    grayscale=False
                )

                if actions_location:
                    action_x, action_y = pyautogui.center(actions_location)
                    pyautogui.click(action_x, action_y)
                    time.sleep(1)

                    # Click specific coordinates
                    pyautogui.click(1198, 878)
                    time.sleep(1)

                    # Press ESC
                    keyboard.press('esc')
                    time.sleep(0.1)
                    keyboard.release('esc')
                    time.sleep(2)

                    # Spam 'à' for 5 seconds
                    start_time = time.time()
                    while time.time() - start_time < 5:
                        keyboard.press('à')
                        time.sleep(0.1)
                        keyboard.release('à')
                        time.sleep(0.2)  # Small delay between presses

                    # Wait additional 10 seconds
                    time.sleep(10)

                    # Set current position to (-5, -23) before restarting
                    self.current_position = (-5, -23)
                    self.log_result("Deposit sequence completed - restarting script at position (-5, -23)")
                    return True

            return False

        except Exception as e:
            self.log_result(f"Sage deposit and restart error: {str(e)}")
            return False
        finally:
            keyboard.release('ctrl')  # Ensure CTRL is released

    def check_heavy_status(self):
        """Check if character is in heavy status by monitoring pixel color or manual trigger."""
        try:
            start_time = time.time()
            while time.time() - start_time < 3:  # Check for 3 seconds
                # Get pixel color at coordinates
                pixel = pyautogui.pixel(1702, 38)
                if pixel == (255, 255, 255):  # Check if pixel is white
                    return True
                time.sleep(0.1)  # Small delay between checks
            return False
        except Exception as e:
            self.log_result(f"Heavy status check error: {str(e)}")
            return False

    def check_low_energy(self):
        """Check if character energy is low by monitoring pixel color."""
        try:
            start_time = time.time()
            while time.time() - start_time < 3:  # Check for 3 seconds
                pixel = pyautogui.pixel(355, 39)
                if pixel != (255, 255, 255):  # Check if pixel is NOT white
                    webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"
                    data = {
                        "content": "<@everyone> ```Warning: Energy is at 30%```"
                    }
                    requests.post(webhook_url, json=data)
                    self.log_result("Low energy detected!")
                    return True
                time.sleep(0.1)

            return False
        except Exception as e:
            self.log_result(f"Energy check error: {str(e)}")
            return False

    def handle_combat(self):
        try:
            Sage_images = [img for img in self.image_paths if "sage" in os.path.basename(img)]

            if Sage_images:
                if self.check_heavy_status():
                    self.log_result("Heavy status detected!")

                    # Store current search state and pause movement
                    temp_searching = self.is_searching
                    self.is_searching = False
                    self.log_result("Pausing movement for bank sequence")

                    # Keep pressing 'à' until zab.png is found
                    zab_found = False
                    max_recall_attempts = 10  # Maximum number of recall attempts
                    recall_attempts = 0

                    while not zab_found and recall_attempts < max_recall_attempts:
                        # Press 'à' to use recall potion
                        self.keyboard_controller.press('à')
                        time.sleep(0.1)
                        self.keyboard_controller.release('à')
                        time.sleep(5)  # Wait for recall animation

                        # Check for zab.png
                        zab_path = os.path.join(self.template_folder, "zab.png")
                        try:
                            zab_location = pyautogui.locateOnScreen(
                                zab_path,
                                confidence=0.9,
                                grayscale=False
                            )
                            if zab_location:
                                zab_found = True
                                self.log_result(f"Found zab.png after {recall_attempts + 1} recall attempts")
                            else:
                                recall_attempts += 1
                                self.log_result(
                                    f"zab.png not found, recall attempt {recall_attempts}/{max_recall_attempts}")
                                time.sleep(2)
                        except Exception as e:
                            recall_attempts += 1
                            self.log_result(f"Error finding zab.png: {str(e)}")
                            time.sleep(2)

                    if zab_found:
                        # Try to find and click zab.png (3 attempts)
                        zab_clicked = False
                        for attempt in range(3):
                            if self.check_and_click_image(zab_path):
                                self.log_result(f"Found and clicked zab.png on attempt {attempt + 1}")
                                zab_clicked = True
                                time.sleep(2)
                                break
                            else:
                                if attempt < 2:  # Don't wait on last attempt
                                    self.log_result(f"zab.png not found, attempt {attempt + 1}/3")
                                    time.sleep(2)

                        if zab_clicked:
                            # Try to find and click astrub.png (3 attempts)
                            astrub_clicked = False
                            for attempt in range(3):
                                astrub_path = os.path.join(self.template_folder, "astrub.png")
                                if self.check_and_click_image(astrub_path):
                                    self.log_result(f"Found and clicked astrub.png on attempt {attempt + 1}")
                                    astrub_clicked = True
                                    time.sleep(2)
                                    break
                                else:
                                    if attempt < 2:
                                        self.log_result(f"astrub.png not found, attempt {attempt + 1}/3")
                                        time.sleep(2)

                            if astrub_clicked:
                                # Try to find and click teleportt.png (3 attempts)
                                teleport_clicked = False
                                for attempt in range(3):
                                    teleport_path = os.path.join(self.template_folder, "teleportt.png")
                                    if self.check_and_click_image(teleport_path):
                                        self.log_result(f"Found and clicked teleportt.png on attempt {attempt + 1}")
                                        teleport_clicked = True
                                        time.sleep(5)  # Wait for teleport
                                        break
                                    else:
                                        if attempt < 2:
                                            self.log_result(f"teleportt.png not found, attempt {attempt + 1}/3")
                                            time.sleep(2)

                                if teleport_clicked:
                                    # Move left
                                    self.execute_move("'")  # Left movement key
                                    time.sleep(5)  # Wait for map load

                                    # Try to find and click bank.png (3 attempts)
                                    bank_clicked = False
                                    for attempt in range(3):
                                        bank_path = os.path.join(self.template_folder, "bank.png")
                                        if self.check_and_click_image(bank_path):
                                            self.log_result(f"Found and clicked bank.png on attempt {attempt + 1}")
                                            bank_clicked = True
                                            time.sleep(6)
                                            break
                                        else:
                                            if attempt < 2:
                                                self.log_result(f"bank.png not found, attempt {attempt + 1}/3")
                                                time.sleep(2)

                                    if bank_clicked:
                                        # Try to find and click banker.png (3 attempts)
                                        banker_clicked = False
                                        for attempt in range(3):
                                            banker_path = os.path.join(self.template_folder, "banker.png")
                                            if self.check_and_click_image(banker_path):
                                                self.log_result(
                                                    f"Found and clicked banker.png on attempt {attempt + 1}")
                                                banker_clicked = True
                                                time.sleep(1)
                                                pyautogui.click(1357, 467)
                                                time.sleep(2)
                                                break
                                            else:
                                                if attempt < 2:
                                                    self.log_result(f"banker.png not found, attempt {attempt + 1}/3")
                                                    time.sleep(2)

                                        if banker_clicked:
                                            # Try all three Sage inventory images with 3 attempts each
                                            sage_found = False
                                            sage_variants = ["Sage-inv.png", "Sage-inv2.png", "Sage-inv3.png"]

                                            for variant in sage_variants:
                                                if sage_found:
                                                    break

                                                for attempt in range(3):
                                                    try:
                                                        sage_path = os.path.join(self.template_folder, variant)
                                                        if os.path.exists(sage_path):
                                                            self.log_result(
                                                                f"Attempting to find {variant} (attempt {attempt + 1}/3)")
                                                            # Expanded search region
                                                            sage_location = pyautogui.locateOnScreen(
                                                                sage_path,
                                                                confidence=0.8,  # Slightly lower confidence
                                                                region=(800, 100, 500, 800),  # Expanded region
                                                                grayscale=False
                                                            )

                                                            if sage_location:
                                                                self.log_result(
                                                                    f"Found Sage using {variant} on attempt {attempt + 1}")
                                                                x, y = pyautogui.center(sage_location)
                                                                self.log_result(
                                                                    f"Clicking Sage at coordinates: ({x}, {y})")
                                                                keyboard.press('ctrl')
                                                                time.sleep(0.1)
                                                                pyautogui.click(x, y)
                                                                time.sleep(0.1)
                                                                keyboard.release('ctrl')
                                                                time.sleep(1)
                                                                sage_found = True
                                                                break
                                                            else:
                                                                self.log_result(
                                                                    f"Could not find {variant} on attempt {attempt + 1}")
                                                        else:
                                                            self.log_result(
                                                                f"Warning: {variant} does not exist in template folder")
                                                    except Exception as e:
                                                        self.log_result(f"Error searching for {variant}: {str(e)}")

                                                    if not sage_found and attempt < 2:
                                                        self.log_result(
                                                            f"Waiting before next attempt to find {variant}")
                                                        time.sleep(2)

                                            if not sage_found:
                                                self.log_result("Failed to find any Sage variants in inventory")
                                                # Optional: take a screenshot for debugging
                                                try:
                                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                                    screenshot = pyautogui.screenshot()
                                                    screenshot.save(f"sage_search_failed_{timestamp}.png")
                                                    self.log_result("Saved debug screenshot of failed Sage search")
                                                except Exception as e:
                                                    self.log_result(f"Failed to save debug screenshot: {str(e)}")

                                            if sage_found:
                                                # Try to find and click actions.png (3 attempts)
                                                actions_clicked = False
                                                for attempt in range(3):
                                                    actions_path = os.path.join(self.template_folder, "actions.png")
                                                    actions_location = pyautogui.locateOnScreen(
                                                        actions_path,
                                                        confidence=0.9,
                                                        region=(833, 163, 1246 - 833, 898 - 163),
                                                        grayscale=False
                                                    )

                                                    if actions_location:
                                                        self.log_result(
                                                            f"Found and clicked actions.png on attempt {attempt + 1}")
                                                        action_x, action_y = pyautogui.center(actions_location)
                                                        pyautogui.click(action_x, action_y)
                                                        actions_clicked = True
                                                        time.sleep(1)
                                                        break
                                                    else:
                                                        if attempt < 2:
                                                            self.log_result(
                                                                f"actions.png not found, attempt {attempt + 1}/3")
                                                            time.sleep(2)

                                                if actions_clicked:
                                                    # Click specific coordinates for deposit
                                                    pyautogui.click(1198, 878)
                                                    time.sleep(1)

                                                    # Press ESC to close bank interface
                                                    keyboard.press('esc')
                                                    time.sleep(0.1)
                                                    keyboard.release('esc')
                                                    time.sleep(2)

                                                    # Use recall potion to return to start
                                                    self.keyboard_controller.press('à')
                                                    time.sleep(0.1)
                                                    self.keyboard_controller.release('à')
                                                    time.sleep(2)

                                                    # Reset position to start of path
                                                    self.current_position = self.path[0]
                                                    self.log_result("Position reset to start after bank sequence")

                                                    # Resume movement
                                                    self.is_searching = temp_searching
                                                    self.log_result("Resuming movement after bank sequence")

                abandon_found = False
                for abandon_variant in ["Abandon.png", "Abandon2.png", "Abandon3.png", "Abandon4.png"]:
                    if self.check_and_click_image(os.path.join(self.template_folder, abandon_variant)):
                        abandon_found = True
                        self.log_result(f"Found and clicked {abandon_variant}")
                        time.sleep(2)
                        break

                if abandon_found:
                    if self.check_and_click_image(os.path.join(self.template_folder, "confirm-leave.png")):
                        time.sleep(2)
                        # Replace close.png check with ESC keypress
                        keyboard.press('esc')
                        time.sleep(0.1)
                        keyboard.release('esc')
                        time.sleep(2)

                        webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"
                        data = {
                            "content": "<@everyone> ```Combat Abandoned```"
                        }
                        requests.post(webhook_url, json=data)

                        # Temporarily pause script
                        temp_searching = self.is_searching
                        self.is_searching = False
                        self.log_result("Pausing script for food clicking sequence")

                        # Click specified location for 5 seconds
                        click_x = 1124
                        click_y = 950
                        start_time = time.time()
                        self.log_result("Starting to click food location")

                        # Move mouse once at the start
                        pyautogui.moveTo(click_x, click_y, duration=0.1)

                        while time.time() - start_time < 5:  # Loop for 5 seconds
                            input_down = INPUT()
                            input_up = INPUT()
                            input_down.type = INPUT_MOUSE
                            input_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
                            input_up.type = INPUT_MOUSE
                            input_up.mi.dwFlags = MOUSEEVENTF_LEFTUP

                            user32.SendInput(1, ctypes.byref(input_down), ctypes.sizeof(INPUT))
                            time.sleep(0.1)  # Delay between down and up
                            user32.SendInput(1, ctypes.byref(input_up), ctypes.sizeof(INPUT))
                            time.sleep(0.1)  # Delay between clicks

                        self.log_result("Finished clicking food location")

                        # Move mouse to center of screen
                        screen_width, screen_height = pyautogui.size()
                        center_x = screen_width // 2
                        center_y = screen_height // 2
                        pyautogui.moveTo(center_x, center_y, duration=0.2)

                        # Resume script
                        self.is_searching = temp_searching
                        self.log_result("Resuming script after food clicking sequence")

                        time.sleep(5)
                        zaap_path = os.path.join(self.template_folder, "Zaap.png")
                        if os.path.exists(zaap_path) and self.check_and_click_image(zaap_path):
                            self.log_result("Zaap found - resetting to start position")
                            self.current_position = self.path[0]
                        return True
                    return False

            return False

        except Exception as e:
            self.log_result(f"Combat handling error: {str(e)}")
            # Make sure to restore script state even if error occurs
            if 'temp_searching' in locals():
                self.is_searching = temp_searching
            return False

    def search_loop(self):
        last_click_check = 0  # Initialize time tracker
        last_abobo_check = 0  # Initialize abobo check timer

        while self.is_searching:
            try:
                current_time = time.time()

                # Inside search_loop method, replace the abobo check with:
                if current_time - last_abobo_check >= 30:
                    abobo_path = os.path.join(self.template_folder, "abobo.png")
                    try:
                        if os.path.exists(abobo_path):
                            abobo_location = pyautogui.locateOnScreen(
                                abobo_path,
                                confidence=0.9,
                                grayscale=False
                            )
                            if abobo_location:
                                self.log_result("Abobo detected - pressing ESC")
                                # Random delay before pressing ESC (150-300ms)
                                time.sleep(random.uniform(0.15, 0.3))
                                # Press ESC with natural hold duration (60-120ms)
                                keyboard.press('esc')
                                time.sleep(random.uniform(0.06, 0.12))
                                keyboard.release('esc')
                                # Random delay after key press (200-400ms)
                                time.sleep(random.uniform(0.2, 0.4))

                                webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"
                                data = {
                                    "content": "<@everyone> ```Combat Abandoned (Abobo)```"
                                }
                                requests.post(webhook_url, json=data)

                                # Temporarily pause script
                                temp_searching = self.is_searching
                                self.is_searching = False
                                self.log_result("Pausing script for food clicking sequence")

                                # Click specified location for 5 seconds
                                click_x = 1124
                                click_y = 950
                                start_time = time.time()
                                self.log_result("Starting to click food location")

                                # Move mouse once at the start
                                pyautogui.moveTo(click_x, click_y, duration=0.1)

                                while time.time() - start_time < 5:  # Loop for 5 seconds
                                    input_down = INPUT()
                                    input_up = INPUT()
                                    input_down.type = INPUT_MOUSE
                                    input_down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
                                    input_up.type = INPUT_MOUSE
                                    input_up.mi.dwFlags = MOUSEEVENTF_LEFTUP

                                    user32.SendInput(1, ctypes.byref(input_down), ctypes.sizeof(INPUT))
                                    time.sleep(0.1)  # Delay between down and up
                                    user32.SendInput(1, ctypes.byref(input_up), ctypes.sizeof(INPUT))
                                    time.sleep(0.1)  # Delay between clicks

                                self.log_result("Finished clicking food location")

                                # Move mouse to center of screen
                                screen_width, screen_height = pyautogui.size()
                                center_x = screen_width // 2
                                center_y = screen_height // 2
                                pyautogui.moveTo(center_x, center_y, duration=0.2)

                                # Resume script
                                self.is_searching = temp_searching
                                self.log_result("Resuming script after food clicking sequence")

                                time.sleep(5)
                                zaap_path = os.path.join(self.template_folder, "Zaap.png")
                                if os.path.exists(zaap_path) and self.check_and_click_image(zaap_path):
                                    self.log_result("Zaap found - resetting to start position")
                                    self.current_position = self.path[0]
                                    continue

                    except Exception as e:
                        self.log_result(f"Abobo check error: {str(e)}")
                    last_abobo_check = current_time

                # Check for click timeout
                if self.check_click_timeout():
                    continue

                # Check for click.png periodically regardless of mode
                if current_time - last_click_check >= 1:  # Check every second
                    if self.check_and_handle_click():
                        last_click_check = current_time
                        continue  # Skip other checks if click sequence was handled

                # Check for shit.png
                if self.check_shit_image():
                    self.log_result("shit.png detected - restarting Dofus")
                    self.is_searching = False
                    self.restart_dofus()
                    break

                next_pos = self.get_next_position()
                if not next_pos:
                    self.is_searching = False
                    break

                self.navigate_to_position(next_pos)
                time.sleep(4)  # delay after reaching a new grid

                # Check for Zaap
                zaap_path = os.path.join(self.template_folder, "Zaap.png")
                if os.path.exists(zaap_path) and self.check_and_click_image(zaap_path):
                    self.log_result("Zaap found - resetting to start position")
                    self.current_position = self.path[0]  # Reset to starting position
                    continue

                pos_str = f"{next_pos[0]},{next_pos[1]}"
                time.sleep(0.3)  # added delay before checking the images
                matching_images = [
                    img for img in self.image_paths
                    if pos_str in os.path.basename(img)
                ]

                for img_path in matching_images:
                    if not self.is_searching:
                        break

                    if self.check_and_click_image(img_path):
                        time.sleep(5)
                        self.handle_combat()

            except Exception as e:
                self.log_result(f"Search error: {str(e)}")
                time.sleep(1)

    def toggle_search_hotkey(self, mode):
        """Toggle search with specified mode (hdv or bank)"""
        self.mode = mode
        self.root.after(0, self.toggle_search)

    def toggle_search(self):
        if not self.is_searching:
            if not self.image_paths:
                messagebox.showerror("Error", "No images loaded!")
                return

            # Focus Dofus window before starting
            if not self.focus_dofus_window():
                messagebox.showerror("Error", "Could not find Dofus window!")
                return

            self.is_searching = True
            self.search_btn.configure(text="Stop Search")

            # Start screenshot monitor before search loop
            self.start_screenshot_monitor()
            threading.Thread(target=self.search_loop, daemon=True).start()
        else:
            self.is_searching = False
            self.search_btn.configure(text="Start Search (F3)")

    def emergency_stop(self):
        self.is_searching = False
        self.status_var.set("Emergency Stop!")
        self.search_btn.configure(text="Start Search (F3)")
        self.log_result("Emergency stop activated")

    def log_result(self, message):
        self.results_text.insert(tk.END, f"{time.strftime('%H:%M:%S')}: {message}\n")
        self.results_text.see(tk.END)
        if "Click error" not in message:
            self.send_discord_webhook(f"{time.strftime('%H:%M:%S')}: {message}")

    def send_discord_webhook(self, message):
        webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"  # Replace with your Discord webhook URL
        try:
            data = {
                "content": f"```{message}```"
            }
            requests.post(webhook_url, json=data)
        except Exception as e:
            print(f"Failed to send webhook: {str(e)}")

    def start_screenshot_monitor(self):
        """Start screenshot monitoring in a separate thread"""

        def screenshot_loop():
            webhook_url = "https://discord.com/api/webhooks/1338964478666080287/b2GFHJNemyk9zR7sdzMQncRPNwZYUqJ_kdSShQV8-wIfdTi3ZYsonmSCBYab5K5FLNdu"

            while self.is_searching:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    screenshot = pyautogui.screenshot()
                    screenshot.save(filename)

                    with open(filename, 'rb') as f:
                        files = {'file': f}
                        response = requests.post(webhook_url, files=files)
                        response.raise_for_status()
                    self.log_result(f"Screenshot sent at {timestamp} ({self.mode} mode)")

                except Exception as e:
                    self.log_result(f"Screenshot error: {str(e)}")
                finally:
                    if os.path.exists(filename):
                        os.remove(filename)

                time.sleep(120)  # 2 minute interval (changed from 300)

        threading.Thread(target=screenshot_loop, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = Locator(root)
    root.mainloop()
