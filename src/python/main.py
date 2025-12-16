#!/usr/bin/env python3
"""
OAK Smart Camera Controller
Main application entry point for Zero-Dep OAK virtual camera system
"""

import sys
import os
import threading
import queue
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QPushButton, QComboBox,
    QGroupBox, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap

try:
    import depthai as dai
except ImportError:
    print("Error: depthai library not found. Please install with: pip install depthai")
    sys.exit(1)

try:
    import pyvirtualcam
except ImportError:
    print("Error: pyvirtualcam library not found. Please install with: pip install pyvirtualcam")
    sys.exit(1)


class Signals(QObject):
    """Thread-safe signals for communication between pipeline and GUI"""
    status_changed = pyqtSignal(str)
    device_connected = pyqtSignal()
    device_disconnected = pyqtSignal()


class OAKPipeline:
    """Handles the OAK device pipeline and frame capture"""

    def __init__(self):
        self.device: Optional[dai.Device] = None
        self.pipeline = None
        self.rgb_queue = None
        self.control_queue = None
        self.running = False
        self.camera = None

    def create_pipeline(self):
        """Create the OAK pipeline configuration"""
        self.pipeline = dai.Pipeline()

        # Define sources and outputs
        self.camera = self.pipeline.create(dai.node.ColorCamera)
        manip = self.pipeline.create(dai.node.ImageManip)
        xout = self.pipeline.create(dai.node.XLinkOut)
        xin = self.pipeline.create(dai.node.XLinkIn)

        # Configure camera
        self.camera.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        self.camera.setInterleaved(True)
        self.camera.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)

        # Configure image manipulation for RGB conversion
        manip.setMaxOutputFrameSize(1920 * 1080 * 3)
        manip.initialConfig.setResizeThumbnail(1920, 1080)

        # Link nodes
        self.camera.preview.link(manip.inputImage)
        manip.out.link(xout.input)

        # Configure XLink
        xout.setStreamName("rgb")
        xin.setStreamName("control")

        return self.pipeline

    def connect_device(self):
        """Connect to OAK device"""
        try:
            # Get first available device
            device_info = dai.DeviceBootloader.getFirstAvailableDevice()
            if not device_info:
                return False

            # Create pipeline
            pipeline = self.create_pipeline()

            # Connect to device
            self.device = dai.Device(pipeline, device_info)

            # Get queues
            self.rgb_queue = self.device.getOutputQueue("rgb", 1, True)
            self.control_queue = self.device.getInputQueue("control")

            self.running = True
            return True

        except Exception as e:
            print(f"Error connecting to device: {e}")
            return False

    def disconnect_device(self):
        """Disconnect from OAK device"""
        self.running = False
        if self.device:
            self.device.close()
            self.device = None
        self.rgb_queue = None
        self.control_queue = None

    def get_frame(self):
        """Get next frame from device"""
        if self.rgb_queue:
            try:
                packet = self.rgb_queue.get(timeout=100)  # 100ms timeout
                return packet.getCvFrame()
            except Exception:
                return None
        return None

    def send_control(self, ctrl: dai.CameraControl):
        """Send control command to device"""
        if self.control_queue:
            self.control_queue.send(ctrl)


class CameraControls(QWidget):
    """Camera control panel widget"""

    def __init__(self, pipeline: OAKPipeline):
        super().__init__()
        self.pipeline = pipeline
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Focus Controls
        focus_group = QGroupBox("Focus")
        focus_layout = QVBoxLayout()

        self.focus_slider = QSlider(Qt.Orientation.Horizontal)
        self.focus_slider.setRange(0, 255)
        self.focus_slider.valueChanged.connect(self.on_focus_changed)

        self.autofocus_btn = QPushButton("Auto Focus")
        self.autofocus_btn.clicked.connect(self.trigger_autofocus)

        focus_layout.addWidget(QLabel("Manual Focus:"))
        focus_layout.addWidget(self.focus_slider)
        focus_layout.addWidget(self.autofocus_btn)
        focus_group.setLayout(focus_layout)

        # Exposure Controls
        exposure_group = QGroupBox("Exposure")
        exposure_layout = QVBoxLayout()

        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(1, 33000)  # microseconds
        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)

        self.iso_slider = QSlider(Qt.Orientation.Horizontal)
        self.iso_slider.setRange(100, 1600)
        self.iso_slider.valueChanged.connect(self.on_iso_changed)

        self.auto_exposure_cb = QCheckBox("Auto Exposure")
        self.auto_exposure_cb.stateChanged.connect(self.on_auto_exposure_changed)

        exposure_layout.addWidget(QLabel("Exposure (μs):"))
        exposure_layout.addWidget(self.exposure_slider)
        exposure_layout.addWidget(QLabel("ISO:"))
        exposure_layout.addWidget(self.iso_slider)
        exposure_layout.addWidget(self.auto_exposure_cb)
        exposure_group.setLayout(exposure_layout)

        # White Balance Controls
        wb_group = QGroupBox("White Balance")
        wb_layout = QVBoxLayout()

        self.wb_slider = QSlider(Qt.Orientation.Horizontal)
        self.wb_slider.setRange(1000, 12000)  # Kelvin
        self.wb_slider.setValue(6500)
        self.wb_slider.valueChanged.connect(self.on_wb_changed)

        wb_layout.addWidget(QLabel("Color Temperature (K):"))
        wb_layout.addWidget(self.wb_slider)
        wb_group.setLayout(wb_layout)

        # Add all groups to main layout
        layout.addWidget(focus_group)
        layout.addWidget(exposure_group)
        layout.addWidget(wb_group)
        layout.addStretch()

        self.setLayout(layout)

    def on_focus_changed(self, value):
        """Handle manual focus change"""
        if self.pipeline.device:
            ctrl = dai.CameraControl()
            ctrl.setManualFocus(value)
            self.pipeline.send_control(ctrl)

    def trigger_autofocus(self):
        """Trigger autofocus"""
        if self.pipeline.device:
            ctrl = dai.CameraControl()
            ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
            ctrl.setAutoFocusTrigger()
            self.pipeline.send_control(ctrl)

    def on_exposure_changed(self, value):
        """Handle exposure time change"""
        if self.pipeline.device and not self.auto_exposure_cb.isChecked():
            ctrl = dai.CameraControl()
            ctrl.setManualExposure(value, self.iso_slider.value())
            self.pipeline.send_control(ctrl)

    def on_iso_changed(self, value):
        """Handle ISO sensitivity change"""
        if self.pipeline.device and not self.auto_exposure_cb.isChecked():
            ctrl = dai.CameraControl()
            ctrl.setManualExposure(self.exposure_slider.value(), value)
            self.pipeline.send_control(ctrl)

    def on_auto_exposure_changed(self, state):
        """Handle auto exposure toggle"""
        if self.pipeline.device:
            ctrl = dai.CameraControl()
            if state == Qt.CheckState.Checked.value:
                ctrl.setAutoExposureEnable()
            else:
                ctrl.setManualExposure(
                    self.exposure_slider.value(),
                    self.iso_slider.value()
                )
            self.pipeline.send_control(ctrl)

    def on_wb_changed(self, value):
        """Handle white balance change"""
        if self.pipeline.device:
            ctrl = dai.CameraControl()
            ctrl.setManualWhiteBalance(value)
            self.pipeline.send_control(ctrl)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.pipeline = OAKPipeline()
        self.signals = Signals()
        self.virtual_camera = None
        self.pipeline_thread = None
        self.control_queue = queue.Queue()
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        self.setWindowTitle("OAK Smart Camera Controller")
        self.setGeometry(100, 100, 400, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Status label
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("QLabel { font-weight: bold; }")
        layout.addWidget(self.status_label)

        # Camera controls
        self.controls = CameraControls(self.pipeline)
        self.controls.setEnabled(False)
        layout.addWidget(self.controls)

        # Control buttons
        btn_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        btn_layout.addWidget(self.connect_btn)

        layout.addLayout(btn_layout)

        central_widget.setLayout(layout)

    def setup_connections(self):
        """Setup signal connections"""
        self.signals.status_changed.connect(self.update_status)
        self.signals.device_connected.connect(self.on_device_connected)
        self.signals.device_disconnected.connect(self.on_device_disconnected)

    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(f"Status: {message}")

    def on_device_connected(self):
        """Handle device connection"""
        self.controls.setEnabled(True)
        self.connect_btn.setText("Disconnect")

    def on_device_disconnected(self):
        """Handle device disconnection"""
        self.controls.setEnabled(False)
        self.connect_btn.setText("Connect")

    def toggle_connection(self):
        """Toggle device connection"""
        if not self.pipeline.running:
            self.connect_device()
        else:
            self.disconnect_device()

    def connect_device(self):
        """Connect to OAK device"""
        self.signals.status_changed.emit("Connecting...")

        if self.pipeline.connect_device():
            self.signals.device_connected.emit()
            self.start_pipeline()
            self.signals.status_changed.emit("Connected")
        else:
            self.signals.status_changed.emit("Connection Failed")
            QMessageBox.warning(self, "Error", "Failed to connect to OAK device")

    def disconnect_device(self):
        """Disconnect from OAK device"""
        self.stop_pipeline()
        self.pipeline.disconnect_device()
        self.signals.device_disconnected.emit()
        self.signals.status_changed.emit("Disconnected")

    def start_pipeline(self):
        """Start the pipeline thread"""
        self.pipeline_thread = threading.Thread(target=self.pipeline_loop, daemon=True)
        self.pipeline_thread.start()

    def stop_pipeline(self):
        """Stop the pipeline thread"""
        self.pipeline.running = False
        if self.pipeline_thread:
            self.pipeline_thread.join(timeout=1.0)

    def pipeline_loop(self):
        """Main pipeline loop for frame capture"""
        # Initialize virtual camera
        try:
            self.virtual_camera = pyvirtualcam.Camera(
                width=1920,
                height=1080,
                fps=30,
                fmt=pyvirtualcam.PixelFormat.BGR
            )
        except Exception as e:
            print(f"Failed to initialize virtual camera: {e}")
            return

        print(f"Virtual camera started: {self.virtual_camera.device}")

        while self.pipeline.running:
            # Get frame from OAK
            frame = self.pipeline.get_frame()

            if frame is not None:
                # Send frame to virtual camera
                self.virtual_camera.send(frame)

            # Process control commands
            try:
                while not self.control_queue.empty():
                    cmd = self.control_queue.get_nowait()
                    # Handle control commands here
            except queue.Empty:
                pass

            # Maintain frame rate
            self.virtual_camera.sleep_until_next_frame()

    def closeEvent(self, event):
        """Handle application close"""
        self.disconnect_device()
        if self.virtual_camera:
            self.virtual_camera.close()
        event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()