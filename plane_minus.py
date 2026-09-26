import sys
import time
import math
import random
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QVariantAnimation, QRectF, QPointF
from PySide6.QtGui import (
    QFont, QPainter, QPainterPath, QPen, QColor, QLinearGradient,
    QPixmap, QPolygonF, QTransform
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QGraphicsOpacityEffect,
    QMessageBox, QSizePolicy, QDialog, QSpinBox, QComboBox,
    QFormLayout, QDialogButtonBox
)

NUMBER_PALETTE = [
    "#FF8A65", "#FFB74D", "#AED581", "#4FC3F7",
    "#BA68C8", "#F06292", "#4DB6AC", "#FFD54F", "#90A4AE",
]


def color_for_number(n):
    return NUMBER_PALETTE[n % len(NUMBER_PALETTE)]

MAX_ALTITUDE = 10       # 飛機跑道終點，對應 win_score
MAX_LIVES = 3
HOP_DURATION_MS = 500    # 每答一題，沿著弧線飛的那一小段時間
ARC_HEIGHT_PX = 90       # 整條拋物線的最高高度（相對於基準線）
LAND_WIDTH = 100         # 起點陸地／終點小島的寬度
HORIZON_RATIO = 0.62     # 海平面在天空面板中的高度比例


class SkyWidget(QWidget):
    """畫出天空、海面、起點陸地、終點小島，以及一條固定的拋物線飛行軌跡（虛線）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path_points = None  # list of (x, y) sample points along the flight path

    def set_path(self, points):
        self._path_points = points
        self.update()

    def paintEvent(self, event):
        rect = self.rect()
        radius = 16

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(clip_path)

        # 天空
        sky_gradient = QLinearGradient(0, 0, 0, rect.height())
        sky_gradient.setColorAt(0.0, QColor("#42A5F5"))
        sky_gradient.setColorAt(1.0, QColor("#E3F2FD"))
        painter.fillRect(rect, sky_gradient)

        horizon_y = rect.height() * HORIZON_RATIO
        ground_rect = QRectF(0, horizon_y, rect.width(), rect.height() - horizon_y)

        # 海面（中間）
        sea_gradient = QLinearGradient(0, horizon_y, 0, rect.height())
        sea_gradient.setColorAt(0.0, QColor("#4FC3F7"))
        sea_gradient.setColorAt(1.0, QColor("#01579B"))
        painter.fillRect(ground_rect, sea_gradient)

        # 海浪紋路
        painter.setPen(QPen(QColor(255, 255, 255, 110), 2))
        for row in range(3):
            wy = horizon_y + 16 + row * 20
            path = QPainterPath()
            path.moveTo(0, wy)
            x, step, up = 0, 26, True
            while x < rect.width():
                path.quadTo(x + step / 2, wy + (8 if up else -8), x + step, wy)
                x += step
                up = not up
            painter.drawPath(path)

        # 起點陸地（左）與終點小島（右）
        land_gradient = QLinearGradient(0, horizon_y, 0, rect.height())
        land_gradient.setColorAt(0.0, QColor("#81C784"))
        land_gradient.setColorAt(1.0, QColor("#2E7D32"))
        painter.fillRect(QRectF(0, horizon_y, LAND_WIDTH, rect.height() - horizon_y), land_gradient)
        painter.fillRect(QRectF(rect.width() - LAND_WIDTH, horizon_y, LAND_WIDTH, rect.height() - horizon_y), land_gradient)

        # 海平面線
        painter.setPen(QPen(QColor(255, 255, 255, 170), 2))
        painter.drawLine(QPointF(0, horizon_y), QPointF(rect.width(), horizon_y))

        # 拋物線飛行軌跡
        if self._path_points and len(self._path_points) >= 2:
            painter.setPen(QPen(QColor(255, 255, 255, 220), 3, Qt.DashLine))
            path = QPainterPath()
            path.moveTo(*self._path_points[0])
            for point in self._path_points[1:]:
                path.lineTo(*point)
            painter.drawPath(path)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#90A4AE"), 2))
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)


def create_plane_pixmap(width=92, height=62, show_gear=False):
    """畫一架卡通風格的客機側面造型（機頭朝右，0 度為水平向右）。"""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    w, h = width, height
    nose = QPointF(w * 0.97, h * 0.52)

    # 機身
    fuselage = QPainterPath()
    fuselage.moveTo(nose)
    fuselage.quadTo(QPointF(w * 0.55, h * 0.16), QPointF(w * 0.12, h * 0.36))
    fuselage.quadTo(QPointF(w * 0.04, h * 0.5), QPointF(w * 0.12, h * 0.64))
    fuselage.quadTo(QPointF(w * 0.55, h * 0.84), nose)
    fuselage.closeSubpath()
    painter.setPen(QPen(QColor("#37474F"), 1.6))
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawPath(fuselage)

    # 機腹陰影
    belly = QPainterPath()
    belly.moveTo(QPointF(w * 0.15, h * 0.55))
    belly.quadTo(QPointF(w * 0.55, h * 0.8), QPointF(w * 0.93, h * 0.56))
    belly.quadTo(QPointF(w * 0.55, h * 0.72), QPointF(w * 0.15, h * 0.55))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#CFD8DC"))
    painter.drawPath(belly)

    # 主機翼（後掠）
    wing = QPolygonF([
        QPointF(w * 0.52, h * 0.52),
        QPointF(w * 0.18, h * 1.0),
        QPointF(w * 0.4, h * 0.88),
        QPointF(w * 0.64, h * 0.58),
    ])
    painter.setPen(QPen(QColor("#37474F"), 1.2))
    painter.setBrush(QColor("#ECEFF1"))
    painter.drawPolygon(wing)

    # 引擎
    painter.setBrush(QColor("#455A64"))
    painter.drawRoundedRect(QRectF(w * 0.36, h * 0.72, w * 0.14, h * 0.24), 4, 4)

    # 尾翼（垂直尾翼）
    tail_fin = QPolygonF([
        QPointF(w * 0.15, h * 0.38),
        QPointF(w * 0.02, h * 0.04),
        QPointF(w * 0.25, h * 0.34),
    ])
    painter.setBrush(QColor("#B71C1C"))
    painter.drawPolygon(tail_fin)

    # 金色腰線
    stripe = QPainterPath()
    stripe.moveTo(QPointF(w * 0.14, h * 0.5))
    stripe.quadTo(QPointF(w * 0.55, h * 0.66), QPointF(w * 0.95, h * 0.52))
    painter.setPen(QPen(QColor("#FFB300"), 3))
    painter.drawPath(stripe)

    # 駕駛艙窗
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#263238"))
    painter.drawEllipse(QPointF(w * 0.86, h * 0.46), w * 0.03, h * 0.05)

    # 客艙窗戶列
    painter.setBrush(QColor("#607D8B"))
    x = w * 0.3
    while x < w * 0.78:
        painter.drawEllipse(QPointF(x, h * 0.44), w * 0.012, h * 0.03)
        x += w * 0.06

    # 起落架：只有起飛前與降落後的地面狀態顯示。
    if show_gear:
        painter.setPen(QPen(QColor("#263238"), 2.0))
        painter.drawLine(QPointF(w * 0.42, h * 0.72), QPointF(w * 0.42, h * 0.91))
        painter.drawLine(QPointF(w * 0.72, h * 0.67), QPointF(w * 0.72, h * 0.87))
        painter.setBrush(QColor("#263238"))
        painter.drawEllipse(QPointF(w * 0.42, h * 0.93), w * 0.045, h * 0.045)
        painter.drawEllipse(QPointF(w * 0.72, h * 0.89), w * 0.045, h * 0.045)

    painter.end()
    return pixmap


GRID_SIZE_OPTIONS = ["2x2", "3x3", "4x4", "5x5"]
GRID_BUTTON_SIZE = {2: 120, 3: 95, 4: 75, 5: 60}
GRID_FONT_SIZE = {2: 22, 3: 20, 4: 16, 5: 13}
DEFAULT_BASE_NUMBER = 100
DEFAULT_GRID_SIZE = 3


class GameSettingsDialog(QDialog):
    """設定遊戲的基準數字與選項格數。"""

    def __init__(self, parent=None, base_number=DEFAULT_BASE_NUMBER, grid_size=DEFAULT_GRID_SIZE):
        super().__init__(parent)
        self.setWindowTitle("遊戲設定")

        layout = QFormLayout(self)

        self.base_spin = QSpinBox()
        self.base_spin.setRange(2, 999)
        self.base_spin.setValue(base_number)
        layout.addRow("用多少去減：", self.base_spin)

        self.grid_combo = QComboBox()
        self.grid_combo.addItems(GRID_SIZE_OPTIONS)
        self.grid_combo.setCurrentText(f"{grid_size}x{grid_size}")
        layout.addRow("格子大小：", self.grid_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        layout.addRow(buttons)

    def get_settings(self):
        base_number = self.base_spin.value()
        grid_size = int(self.grid_combo.currentText()[0])
        return base_number, grid_size


class MakeTenGame(QWidget):
    def __init__(self, base_number=DEFAULT_BASE_NUMBER, grid_size=DEFAULT_GRID_SIZE):
        super().__init__()
        self.base_number = base_number
        self.grid_size = grid_size
        self.grid_count = grid_size * grid_size
        self.setWindowTitle("湊十遊戲")
        self.resize(780, 500)
        self.setStyleSheet("""
            MakeTenGame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #E3F2FD, stop:1 #F3E5F5);
            }
        """)

        self.target_number = 0
        self.grid_buttons = []
        self.score = 0
        self.win_score = 10
        self.lives = MAX_LIVES
        self.altitude = 0
        self.game_over = False
        self.win_result = True
        self.is_animating = False
        self.timer_started = False
        self.start_time = 0.0
        self.elapsed_seconds = 0.0

        self.track_start_x = 0.0
        self.track_end_x = 0.0
        self.track_baseline_y = 0.0

        self._plane_air_pixmap = create_plane_pixmap(92, 62, False)
        self._plane_ground_pixmap = create_plane_pixmap(92, 62, True)

        self._build_ui()
        self._build_end_overlay()
        self.start_new_game()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 上方：飛機跑道（海面 + 起點陸地 + 終點小島 + 固定拋物線）
        self.sky_widget = SkyWidget()
        self.sky_widget.setMinimumHeight(170)
        self.sky_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 左側控制按鈕
        self.restart_btn = QPushButton("↻  重來")
        self.restart_btn.setFixedHeight(38)
        self.restart_btn.setMinimumWidth(92)
        self.restart_btn.clicked.connect(self.restart_game)

        self.settings_btn = QPushButton("⚙  題目設定")
        self.settings_btn.setFixedHeight(38)
        self.settings_btn.setMinimumWidth(112)
        self.settings_btn.clicked.connect(self.change_settings)

        control_style = """
            QPushButton {
                background: rgba(255, 255, 255, 225);
                color: #24445F;
                border: 1px solid rgba(80, 125, 160, 90);
                border-radius: 10px;
                padding: 0 12px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: white;
                border: 1px solid #4C9BD3;
            }
            QPushButton:pressed {
                background: #E7F3FB;
            }
        """
        self.restart_btn.setStyleSheet(control_style)
        self.settings_btn.setStyleSheet(control_style)

        self.plane_label = QLabel(self.sky_widget)
        self.plane_label.setFixedSize(92, 62)
        self.plane_label.setAlignment(Qt.AlignCenter)
        self.plane_label.setFont(QFont("Arial", 28))

        self.finish_pin = QLabel(str(MAX_ALTITUDE), self.sky_widget)
        self.finish_pin.setFixedSize(38, 38)
        self.finish_pin.setAlignment(Qt.AlignCenter)
        self.finish_pin.setFont(QFont("Arial", 14, QFont.Bold))
        self.finish_pin.setStyleSheet("""
            background-color: #E53935;
            color: white;
            border-radius: 19px;
            border: 3px solid white;
        """)

        # 畫面最左上方的控制列
        control_bar = QHBoxLayout()
        control_bar.setContentsMargins(0, 0, 0, 6)
        control_bar.setSpacing(8)
        control_bar.addWidget(self.restart_btn)
        control_bar.addWidget(self.settings_btn)
        control_bar.addStretch(1)
        main_layout.addLayout(control_bar)

        main_layout.addWidget(self.sky_widget)


        # 下方：左側資訊 + 右側九宮格
        bottom_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        self.target_label = QLabel("0")
        self.target_label.setAlignment(Qt.AlignCenter)
        self.target_label.setFont(QFont("Arial", 90, QFont.Bold))
        self.target_label.setStyleSheet("color: #5E35B1;")
        left_layout.addWidget(self.target_label)

        self.status_label = QLabel("請選擇和左邊數字加起來等於 100 的數字")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        self.score_label = QLabel("分數：0 / 10")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.score_label.setStyleSheet("color: #00695C;")
        left_layout.addWidget(self.score_label)

        self.lives_label = QLabel("生命：❤️❤️❤️")
        self.lives_label.setAlignment(Qt.AlignCenter)
        self.lives_label.setFont(QFont("Arial", 16))
        left_layout.addWidget(self.lives_label)

        bottom_layout.addLayout(left_layout, 3)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        self.grid_layout = grid_layout
        bottom_layout.addLayout(grid_layout, 3)
        self._build_grid_buttons()

        main_layout.addLayout(bottom_layout)

    def _build_grid_buttons(self):
        """依目前的 grid_size 建立九宮格按鈕；重新設定格數時會先清除舊按鈕。"""
        for btn in self.grid_buttons:
            self.grid_layout.removeWidget(btn)
            btn.deleteLater()
        self.grid_buttons = []

        btn_size = GRID_BUTTON_SIZE.get(self.grid_size, 90)
        font_size = GRID_FONT_SIZE.get(self.grid_size, 18)
        for i in range(self.grid_count):
            btn = QPushButton()
            btn.setFont(QFont("Arial", font_size, QFont.Bold))
            btn.setFixedSize(btn_size, btn_size)
            btn.clicked.connect(lambda checked=False, b=btn: self.on_number_clicked(b))
            row, col = divmod(i, self.grid_size)
            self.grid_layout.addWidget(btn, row, col)
            self.grid_buttons.append(btn)

    def _build_end_overlay(self):
        self.end_overlay = QWidget(self)
        self.end_overlay.setStyleSheet("background-color: rgba(20, 20, 20, 225);")
        self.end_overlay.hide()

        overlay_layout = QVBoxLayout(self.end_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        self.end_title = QLabel("")
        self.end_title.setAlignment(Qt.AlignCenter)
        self.end_title.setFont(QFont("Arial", 36, QFont.Bold))
        overlay_layout.addWidget(self.end_title)

        self.end_hint = QLabel("點擊畫面可略過動畫")
        self.end_hint.setAlignment(Qt.AlignCenter)
        self.end_hint.setFont(QFont("Arial", 14))
        self.end_hint.setStyleSheet("color: white;")
        overlay_layout.addWidget(self.end_hint)

        self.end_overlay.mousePressEvent = lambda event: self.skip_end_animation()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.end_overlay.setGeometry(self.rect())
        self.update_track_geometry()
        if not self.is_animating:
            self.place_plane(self.altitude / MAX_ALTITUDE)

    # ---- 單一固定飛行曲線的座標與角度計算（起降時保持水平）----
    def update_track_geometry(self):
        half_w = self.plane_label.width() / 2
        half_h = self.plane_label.height() / 2

        self.track_start_x = LAND_WIDTH / 2 - half_w
        self.track_end_x = max(
            self.track_start_x,
            self.sky_widget.width() - LAND_WIDTH / 2 - half_w
        )
        horizon_y = self.sky_widget.height() * HORIZON_RATIO
        self.track_baseline_y = horizon_y - half_h

        sample_count = 60
        points = [
            (
                self.point_on_arc(i / sample_count)[0] + half_w,
                self.point_on_arc(i / sample_count)[1] + half_h,
            )
            for i in range(sample_count + 1)
        ]
        self.sky_widget.set_path(points)
        self.position_finish_pin()

    def point_on_arc(self, t):
        """單一固定飛行曲線：t 從 0（起點陸地）到 1（終點小島）。
        用 (1 - cos) 的曲線讓起飛、降落時的切線都是水平的，不會像拋物線一樣俯衝。"""
        x = self.track_start_x + (self.track_end_x - self.track_start_x) * t
        height = ARC_HEIGHT_PX * (1 - math.cos(2 * math.pi * t)) / 2
        y = self.track_baseline_y - height
        return x, y

    def angle_for_t(self, t):
        """依照飛行曲線切線方向計算飛機的俯仰角（度），機頭朝右為 0 度。
        在 t=0（起飛）與 t=1（降落）時斜率剛好是 0，飛機會保持水平。"""
        dx_dt = self.track_end_x - self.track_start_x
        if dx_dt <= 0:
            return 0.0
        dy_dt = -ARC_HEIGHT_PX * math.pi * math.sin(2 * math.pi * t)
        return math.degrees(math.atan2(dy_dt, dx_dt))

    def place_plane(self, t):
        t = max(0.0, min(1.0, float(t)))
        x, y = self.point_on_arc(t)
        self.plane_label.move(int(x), int(y))

        # 只有真正位於起點／終點地面時才顯示起落架。
        on_ground = t <= 0.0001 or t >= 0.9999
        base_pixmap = self._plane_ground_pixmap if on_ground else self._plane_air_pixmap

        transform = QTransform()
        transform.rotate(self.angle_for_t(t))
        rotated = base_pixmap.transformed(transform, Qt.SmoothTransformation)
        self.plane_label.setPixmap(rotated)

    def position_finish_pin(self):
        x, y = self.point_on_arc(1.0)
        self.finish_pin.move(int(x + self.plane_label.width() - 6), int(y - 4))

    def restart_game(self):
        """重新開始目前的遊戲，不改變題目規格。"""
        if hasattr(self, "_hop_anim") and self._hop_anim.state() == QVariantAnimation.State.Running:
            self._hop_anim.stop()
        self.is_animating = False
        self.score = 0
        self.lives = MAX_LIVES
        self.altitude = 0
        self.game_over = False
        self.win_result = True
        self.start_time = time.time()
        self.elapsed_seconds = 0.0
        self.update_score_label()
        self.update_lives_label()
        self.end_overlay.hide()
        self.place_plane(0.0)
        self.new_round()

    def change_settings(self):
        """重新設定題目規格；取消則維持原本設定。"""
        dialog = GameSettingsDialog(
            self, self.base_number, self.grid_size
        )
        dialog.setWindowTitle("重新設定題目")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.base_number, self.grid_size = dialog.get_settings()
            self.grid_count = self.grid_size * self.grid_size
            self._build_grid_buttons()
            self.restart_game()

    def start_new_game(self):
        self.score = 0
        self.lives = MAX_LIVES
        self.altitude = 0
        self.game_over = False
        self.is_animating = False
        self.timer_started = False
        self.start_time = 0.0
        self.update_score_label()
        self.update_lives_label()
        self.update_track_geometry()
        self.place_plane(0.0)
        self.new_round()

    def new_round(self):
        """產生新題目，並保證正確答案一定出現在選項中。"""
        # target 一定介於 1 與 base_number-1，因此正確答案也一定是正整數。
        self.target_number = random.randint(1, self.base_number - 1)
        correct_answer = self.base_number - self.target_number
        self.target_label.setText(str(self.target_number))

        # 先建立足夠多、且明確排除正確答案的錯誤選項。
        # 保留原本「必要時可超過 base_number」的設計，避免小基準數搭配大格數時無法出題。
        candidate_max = max(self.base_number, self.grid_count + 2)
        pool = [n for n in range(1, candidate_max + 1) if n != correct_answer]

        distractor_count = self.grid_count - 1
        distractors = random.sample(pool, distractor_count)

        # 正確答案最後強制加入，再整體打亂。
        numbers = distractors + [correct_answer]
        random.shuffle(numbers)

        # 防呆：任何情況都不允許正確答案遺失。
        if correct_answer not in numbers:
            raise RuntimeError(
                f"題目產生錯誤：{self.target_number} + ? = {self.base_number}，"
                f"正確答案 {correct_answer} 不在選項中。"
            )

        for btn, num in zip(self.grid_buttons, numbers):
            btn.setText(str(num))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_for_number(num)};
                    border-radius: 12px;
                    color: white;
                    border: 2px solid transparent;
                }}
                QPushButton:hover {{
                    border: 2px solid white;
                }}
                QPushButton:pressed {{
                    border: 3px solid white;
                }}
            """)

        self.status_label.setText(
            f"請選擇和左邊數字加起來等於 {self.base_number} 的數字"
        )

    def on_number_clicked(self, button):
        if self.game_over or self.is_animating:
            return

        if not self.timer_started:
            self.timer_started = True
            self.start_time = time.time()

        chosen = int(button.text())
        old_altitude = self.altitude

        if chosen + self.target_number == self.base_number:
            self.score += 1
            self.altitude = min(MAX_ALTITUDE, self.altitude + 1)
            button.setStyleSheet(button.styleSheet() + "border: 3px solid #2E7D32;")
            self.status_label.setText(f"答對了！{self.target_number} + {chosen} = {self.base_number}，飛機前進一段！")
        else:
            self.score -= 1
            self.lives -= 1
            self.altitude = max(0, self.altitude - 1)
            button.setStyleSheet(button.styleSheet() + "border: 3px solid #C62828;")
            self.status_label.setText("不對喔，飛機退回一段！")

        self.update_score_label()
        self.update_lives_label()
        self.animate_plane(old_altitude, self.altitude)

    def animate_plane(self, from_altitude, to_altitude):
        self.is_animating = True
        t_from = from_altitude / MAX_ALTITUDE
        t_to = to_altitude / MAX_ALTITUDE

        self._hop_anim = QVariantAnimation(self)
        self._hop_anim.setDuration(HOP_DURATION_MS)
        self._hop_anim.setStartValue(t_from)
        self._hop_anim.setEndValue(t_to)
        self._hop_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._hop_anim.valueChanged.connect(self.place_plane)
        self._hop_anim.finished.connect(self.on_hop_finished)
        self._hop_anim.start()

    def on_hop_finished(self):
        self.is_animating = False
        self.place_plane(self.altitude / MAX_ALTITUDE)

        if self.lives <= 0:
            self.show_end_overlay(win=False)
            return

        if self.score >= self.win_score:
            self.show_end_overlay(win=True)
            return

        self.new_round()

    def update_score_label(self):
        self.score_label.setText(f"分數：{self.score} / {self.win_score}")

    def update_lives_label(self):
        hearts = "❤️" * self.lives + "🖤" * (MAX_LIVES - self.lives)
        self.lives_label.setText(f"生命：{hearts}")

    def show_end_overlay(self, win: bool):
        self.game_over = True
        self.win_result = win
        self.elapsed_seconds = time.time() - self.start_time
        self.end_overlay.setGeometry(self.rect())

        if win:
            self.end_title.setText("🎉 恭喜獲勝！ 🎉")
            self.end_title.setStyleSheet("color: #FFD54F;")
        else:
            self.plane_label.setText("💥")
            self.end_title.setText("💥 飛機墜毀，遊戲結束 💥")
            self.end_title.setStyleSheet("color: #EF5350;")

        self._end_opacity_effect = QGraphicsOpacityEffect(self.end_overlay)
        self.end_overlay.setGraphicsEffect(self._end_opacity_effect)
        self.end_overlay.show()
        self.end_overlay.raise_()

        self._end_anim = QPropertyAnimation(self._end_opacity_effect, b"opacity")
        self._end_anim.setDuration(5000)
        self._end_anim.setStartValue(0.0)
        self._end_anim.setEndValue(1.0)
        self._end_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._end_anim.finished.connect(self.show_result_dialog)
        self._end_anim.start()

    def skip_end_animation(self):
        if self._end_anim.state() == QPropertyAnimation.State.Running:
            self._end_anim.stop()
            self._end_opacity_effect.setOpacity(1.0)
            self.show_result_dialog()

    def show_result_dialog(self):
        self.end_overlay.hide()
        if self.win_result:
            QMessageBox.information(
                self, "遊戲結束",
                f"恭喜獲勝！你總共花了 {self.elapsed_seconds:.1f} 秒"
            )
        else:
            QMessageBox.warning(
                self, "遊戲結束",
                f"飛機墜毀了！本局花了 {self.elapsed_seconds:.1f} 秒，最終分數 {self.score} 分"
            )
        self.start_new_game()


def main():
    app = QApplication(sys.argv)

    dialog = GameSettingsDialog()
    if dialog.exec() == QDialog.Accepted:
        base_number, grid_size = dialog.get_settings()
    else:
        base_number, grid_size = DEFAULT_BASE_NUMBER, DEFAULT_GRID_SIZE

    window = MakeTenGame(base_number=base_number, grid_size=grid_size)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
