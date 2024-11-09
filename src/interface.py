import sys
import requests
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QHBoxLayout

from PyQt5.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QGraphicsScene, 
    QGraphicsView, 
    QGraphicsRectItem,
    QGraphicsTextItem,  # Agregada esta importación
    QVBoxLayout, 
    QWidget, 
    QLabel, 
    QHBoxLayout
)
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter
from PyQt5.QtCore import QRectF, Qt

class StadiumAPI:
    """Clase para manejar las llamadas a la API del estadio"""
    BASE_URL = "http://127.0.0.1:8080"

    @staticmethod
    def get_stadium_structure():
        """Obtiene la estructura del estadio desde la API"""
        try:
            response = requests.get(f"{StadiumAPI.BASE_URL}/get_stadium_structure")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error al obtener la estructura del estadio: {e}")
            return None

class Seat(QGraphicsRectItem):
    """Clase para representar un asiento individual"""
    COLORS = {
        "Libre": QColor("green"),
        "Reservado": QColor("yellow"),
        "ReservadoPorUsuario": QColor("orange"),
        "Comprado": QColor("red")
    }

    def __init__(self, x, y, size, row, column, state):
        super().__init__(QRectF(x, y, size, size))
        self.row = row
        self.column = column
        self.state = state
        self.setup_appearance()

    def setup_appearance(self):
        """Configura la apariencia visual del asiento"""
        self.setBrush(QBrush(self.COLORS[self.state]))
        self.setPen(QPen(Qt.black))

class SeatLabel(QGraphicsTextItem):
    """Clase para el texto/número del asiento"""
    def __init__(self, x, y, row, column):
        super().__init__(f"{row+1}-{column+1}")
        self.setPos(x + 5, y + 5)

class ZoneLabel(QGraphicsTextItem):
    """Clase para la etiqueta de zona"""
    def __init__(self, text, x, y):
        super().__init__(f"Zona {text}")
        self.setPos(x, y)

class CategoryLabel(QGraphicsTextItem):
    """Clase para la etiqueta de categoría"""
    def __init__(self, text, x, y):
        super().__init__(f"Categoría {text}")
        self.setPos(x, y)

class StadiumLayout:
    """Clase para manejar el diseño y dimensiones del estadio"""
    def __init__(self):
        self.seat_size = 30
        self.spacing = 5
        self.zone_spacing = 50
        self.current_x = 0
        self.current_y = 0

    def reset_position(self):
        """Reinicia las posiciones actuales"""
        self.current_x = 0
        self.current_y = 0

    def advance_row(self):
        """Avanza a la siguiente fila"""
        self.current_y += self.seat_size + self.spacing
        self.current_x = self.spacing

    def advance_category(self):
        """Avanza a la siguiente categoría"""
        self.current_y += self.spacing * 2

    def advance_zone(self):
        """Avanza a la siguiente zona"""
        self.current_y += self.zone_spacing

class StadiumView(QGraphicsView):
    """Clase principal para la vista del estadio"""
    def __init__(self, estadio):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.layout = StadiumLayout()
        self.setup_view()
        self.draw_stadium_structure(estadio)

    def setup_view(self):
        """Configura las propiedades de la vista"""
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def draw_stadium_structure(self, estadio):
        """Dibuja la estructura completa del estadio"""
        self.layout.reset_position()
        
        for zona in estadio['zonas']:
            self.draw_zone(zona)
            self.layout.advance_zone()

        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def draw_zone(self, zona):
        """Dibuja una zona completa del estadio"""
        self.scene.addItem(ZoneLabel(zona['nombre'], 0, self.layout.current_y))
        self.layout.current_y += 30

        for categoria, asientos in zona['categorias'].items():
            self.draw_category(categoria, asientos)
            self.layout.advance_category()

    def draw_category(self, categoria, asientos):
        """Dibuja una categoría completa con sus asientos"""
        self.scene.addItem(CategoryLabel(categoria, self.layout.spacing, self.layout.current_y))
        self.layout.current_y += 30

        for i, fila in enumerate(asientos):
            self.layout.current_x = self.layout.spacing
            self.draw_row(i, fila)
            self.layout.advance_row()

    def draw_row(self, row_num, fila):
        """Dibuja una fila completa de asientos"""
        for col_num, asiento in enumerate(fila):
            seat = Seat(
                self.layout.current_x,
                self.layout.current_y,
                self.layout.seat_size,
                row_num,
                col_num,
                asiento['estado']
            )
            self.scene.addItem(seat)
            self.scene.addItem(SeatLabel(
                self.layout.current_x,
                self.layout.current_y,
                row_num,
                col_num
            ))
            self.layout.current_x += self.layout.seat_size + self.layout.spacing

    def wheelEvent(self, event):
        """Maneja el evento de la rueda del mouse para zoom"""
        if event.angleDelta().y() > 0:
            self.scale(1.15, 1.15)
        else:
            self.scale(0.85, 0.85)

class LegendWidget(QWidget):
    """Clase para el widget de la leyenda"""
    def __init__(self):
        super().__init__()
        self.setup_legend()

    def setup_legend(self):
        """Configura la leyenda de colores"""
        layout = QHBoxLayout(self)
        states = {
            "Libre": "green",
            "Reservado": "yellow",
            "ReservadoPorUsuario": "orange",
            "Comprado": "red"
        }
        
        for state, color in states.items():
            label = QLabel(f"■ {state}")
            label.setStyleSheet(f"color: {color}")
            layout.addWidget(label)

class StadiumWindow(QMainWindow):
    """Clase principal de la ventana"""
    def __init__(self, estadio):
        super().__init__()
        self.setup_window()
        self.setup_ui(estadio)

    def setup_window(self):
        """Configura las propiedades de la ventana"""
        self.setWindowTitle("Estructura del Estadio")
        self.setGeometry(100, 100, 1000, 800)

    def setup_ui(self, estadio):
        """Configura la interfaz de usuario"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        layout.addWidget(LegendWidget())
        layout.addWidget(StadiumView(estadio))

def main():
    """Función principal de la aplicación"""
    app = QApplication(sys.argv)
    estadio = StadiumAPI.get_stadium_structure()
    
    if estadio:
        window = StadiumWindow(estadio)
        window.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()