import sys
import requests
import json

from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QComboBox,
    QPushButton,
    QMessageBox,
    QLineEdit,
    QDialog,
    QFormLayout,
)
from PyQt5.QtGui import QColor, QPen, QBrush
from PyQt5.QtCore import QRectF, Qt, QTimer, QObject, pyqtSignal, QUrl

from PyQt5.QtWebSockets import QWebSocket

class StadiumAPI:
    BASE_URL = "http://127.0.0.1:8080"

    @staticmethod
    def get_stadium_structure():
        try:
            response = requests.get(f"{StadiumAPI.BASE_URL}/get_stadium_structure")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al obtener la estructura del estadio: {e}")
            return None

    @staticmethod
    def buscar_asientos(categoria, cantidad):
        try:
            response = requests.post(
                f"{StadiumAPI.BASE_URL}/buscar_asientos",
                json={"categoria": categoria, "cantidad": cantidad}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al buscar asientos: {e}")
            return None

    @staticmethod
    def reservar_asientos_temporalmente(zona, categoria, asientos):
        try:
            response = requests.post(
                f"{StadiumAPI.BASE_URL}/reservar_asientos_temporalmente",
                json={
                    "zona": zona,
                    "categoria": categoria,
                    "asientos": asientos
                }
            )
            response.raise_for_status()
            return response.json()  # Debería contener 'reserva_id'
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al reservar asientos temporalmente: {e}")
            return None

    @staticmethod
    def confirmar_compra(reserva_id):
        try:
            response = requests.post(
                f"{StadiumAPI.BASE_URL}/confirmar_compra",
                json={
                    "reserva_id": reserva_id
                }
            )
            response.raise_for_status()
            content = response.text.strip()
            if content == "true":
                return True
            else:
                return False
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al confirmar la compra: {e}")
            return False

    @staticmethod
    def procesar_pago(metodo_pago, detalles):
        try:
            response = requests.post(
                f"{StadiumAPI.BASE_URL}/procesar_pago",
                json={
                    "metodo_pago": metodo_pago,
                    "detalles": detalles
                }
            )
            response.raise_for_status()
            content = response.text.strip()
            if content == "true":
                return {"aprobado": True}
            else:
                return {"aprobado": False}
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al procesar el pago: {e}")
            return {"aprobado": False}

    @staticmethod
    def cancelar_reserva(reserva_id):
        try:
            response = requests.post(
                f"{StadiumAPI.BASE_URL}/cancelar_reserva",
                json={"reserva_id": reserva_id}
            )
            response.raise_for_status()
            content = response.text.strip()
            if content == "true":
                return True
            else:
                return False
        except requests.RequestException as e:
            StadiumAPI.show_error(f"Error al cancelar la reserva: {e}")
            return False

    @staticmethod
    def show_error(message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText(message)
        msg.setWindowTitle("Error")
        msg.exec_()


class Seat(QGraphicsRectItem):
    COLORS = {
        "Libre": QColor("green"),
        "Reservado": QColor("yellow"),
        "ReservadoPorUsuario": QColor("orange"),
        "Comprado": QColor("red"),
        "ReservadoTemporalmente": QColor("purple"),
        "Sugerido": QColor("blue")
    }

    def __init__(self, x, y, size, row, column, state, zona, categoria):
        super().__init__(QRectF(x, y, size, size))
        self.row = row
        self.column = column
        self.state = state
        self.zona = zona
        self.categoria = categoria
        self.setup_appearance()

    def setup_appearance(self):
        self.setBrush(QBrush(self.COLORS.get(self.state, QColor("grey"))))
        self.setPen(QPen(Qt.black))

    def update_state(self, new_state):
        self.state = new_state
        self.setup_appearance()


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
    def __init__(self, estadio):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.layout = StadiumLayout()
        self.seats_map = {}  # Diccionario para mapear asientos
        self.setup_view()
        self.draw_stadium_structure(estadio)

        # Conexión al WebSocket
        self.websocket_client = WebSocketClient()
        self.websocket_client.update_received.connect(self.handle_updates)

    def setup_view(self):
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def draw_stadium_structure(self, estadio):
        self.layout.reset_position()
        self.scene.clear()
        self.seats_map.clear()

        for zona in estadio['zonas']:
            self.draw_zone(zona)
            self.layout.advance_zone()

        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def draw_zone(self, zona):
        self.scene.addItem(ZoneLabel(zona['nombre'], 0, self.layout.current_y))
        self.layout.current_y += 30

        for categoria_key, asientos in zona['categorias'].items():
            categoria = categoria_key
            self.draw_category(zona['nombre'], categoria, asientos)
            self.layout.advance_category()

    def draw_category(self, zona_nombre, categoria, asientos):
        self.scene.addItem(CategoryLabel(categoria, self.layout.spacing, self.layout.current_y))
        self.layout.current_y += 30

        # Crear entrada en el diccionario para esta zona y categoría si no existe
        if zona_nombre not in self.seats_map:
            self.seats_map[zona_nombre] = {}
        if categoria not in self.seats_map[zona_nombre]:
            self.seats_map[zona_nombre][categoria] = []

        for i, fila in enumerate(asientos):
            self.layout.current_x = self.layout.spacing
            row_seats = self.draw_row(i, fila, zona_nombre, categoria)
            self.seats_map[zona_nombre][categoria].extend(row_seats)
            self.layout.advance_row()

    def draw_row(self, row_num, fila, zona_nombre, categoria):
        row_seats = []
        for col_num, asiento in enumerate(fila):
            seat = Seat(
                self.layout.current_x,
                self.layout.current_y,
                self.layout.seat_size,
                row_num,
                col_num,
                asiento['estado'],
                zona_nombre,
                categoria
            )
            self.scene.addItem(seat)
            self.scene.addItem(SeatLabel(
                self.layout.current_x,
                self.layout.current_y,
                row_num,
                col_num
            ))
            row_seats.append(seat)
            self.layout.current_x += self.layout.seat_size + self.layout.spacing
        return row_seats

    def find_seats_in_map(self, zona_nombre, categoria, asientos_list):
        found_seats = []
        if zona_nombre in self.seats_map and categoria in self.seats_map[zona_nombre]:
            for seat in self.seats_map[zona_nombre][categoria]:
                for fila, columna in asientos_list:
                    if seat.row == fila and seat.column == columna:
                        found_seats.append(seat)
        return found_seats

    def reset_suggested_seats(self):
        for zona in self.seats_map.values():
            for categoria in zona.values():
                for seat in categoria:
                    if seat.state == "Sugerido":
                        seat.update_state("Libre")

    def highlight_seats(self, seats):
        self.reset_suggested_seats()
        for seat in seats:
            seat.update_state("Sugerido")

    def handle_updates(self, data):
        for zona in data['zonas']:
            zona_nombre = zona['nombre']
            if zona_nombre in self.seats_map:
                self.update_zone(zona_nombre, zona)

    def update_zone(self, zona_nombre, zona_data):
        for categoria_key, asientos in zona_data['categorias'].items():
            categoria = categoria_key
            if categoria in self.seats_map[zona_nombre]:
                self.update_category(zona_nombre, categoria, asientos)

    def update_category(self, zona_nombre, categoria, asientos_data):
        seats_list = self.seats_map[zona_nombre][categoria]
        for i, fila in enumerate(asientos_data):
            for j, asiento_data in enumerate(fila):
                seat = next((s for s in seats_list if s.row == i and s.column == j), None)
                if seat:
                    new_state = asiento_data['estado']
                    if seat.state != new_state:
                        seat.update_state(new_state)

    def wheelEvent(self, event):
        """Maneja el evento de la rueda del mouse para zoom"""
        if event.angleDelta().y() > 0:
            self.scale(1.15, 1.15)
        else:
            self.scale(0.85, 0.85)


class WebSocketClient(QObject):
    update_received = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.websocket = QWebSocket()
        self.websocket.error.connect(self.on_error)
        self.websocket.textMessageReceived.connect(self.on_message)
        self.websocket.connected.connect(self.on_connected)
        self.websocket.disconnected.connect(self.on_disconnected)
        self.websocket.open(QUrl("ws://127.0.0.1:8080/ws"))

    def on_connected(self):
        print("Conectado al servidor WebSocket.")

    def on_disconnected(self):
        print("Desconectado del servidor WebSocket.")

    def on_message(self, message):
        print("Mensaje recibido del WebSocket")
        data = json.loads(message)
        self.update_received.emit(data)

    def on_error(self, error):
        print(f"WebSocket error: {error}")


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
            "Comprado": "red",
            "ReservadoTemporalmente": "purple",
            "Sugerido": "blue"
        }

        for state, color in states.items():
            label = QLabel(f"■ {state}")
            label.setStyleSheet(f"color: {color}")
            layout.addWidget(label)

## Plugin de pago
class MetodoPago:
    def iniciar_pago(self):
        raise NotImplementedError

    def validar_informacion(self):
        raise NotImplementedError

    def procesar_pago(self):
        raise NotImplementedError


class PagoTarjeta(MetodoPago):
    def __init__(self):
        self.detalles = {}

    def iniciar_pago(self):
        dialog = QDialog()
        dialog.setWindowTitle("Pago con Tarjeta")
        layout = QFormLayout(dialog)
        self.numero_tarjeta = QLineEdit()
        self.cvv = QLineEdit()
        self.fecha_expiracion = QLineEdit()
        layout.addRow("Número de Tarjeta:", self.numero_tarjeta)
        layout.addRow("CVV:", self.cvv)
        layout.addRow("Fecha de Expiración:", self.fecha_expiracion)
        botones = QHBoxLayout()
        boton_aceptar = QPushButton("Aceptar")
        boton_aceptar.clicked.connect(dialog.accept)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(dialog.reject)
        botones.addWidget(boton_aceptar)
        botones.addWidget(boton_cancelar)
        layout.addRow(botones)
        if dialog.exec_() == QDialog.Accepted:
            self.detalles = {
                "numero_tarjeta": self.numero_tarjeta.text(),
                "cvv": self.cvv.text(),
                "fecha_expiracion": self.fecha_expiracion.text()
            }
            return True
        return False

    def validar_informacion(self):
        # Verificar que todos los campos tengan información
        return all(self.detalles.values())

    def procesar_pago(self):
        # Llamar al servidor para procesar el pago
        return StadiumAPI.procesar_pago("Tarjeta", self.detalles)


class PagoPayPal(MetodoPago):
    def __init__(self):
        self.detalles = {}

    def iniciar_pago(self):
        dialog = QDialog()
        dialog.setWindowTitle("Pago con PayPal")
        layout = QFormLayout(dialog)
        self.email = QLineEdit()
        self.password = QLineEdit()
        layout.addRow("Email:", self.email)
        layout.addRow("Contraseña:", self.password)
        botones = QHBoxLayout()
        boton_aceptar = QPushButton("Aceptar")
        boton_aceptar.clicked.connect(dialog.accept)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(dialog.reject)
        botones.addWidget(boton_aceptar)
        botones.addWidget(boton_cancelar)
        layout.addRow(botones)
        if dialog.exec_() == QDialog.Accepted:
            self.detalles = {
                "email": self.email.text(),
                "password": self.password.text(),
            }
            return True
        return False

    def validar_informacion(self):
        # Verificar que todos los campos tengan información
        return all(self.detalles.values())

    def procesar_pago(self):
        # Llamar al servidor para procesar el pago
        return StadiumAPI.procesar_pago("PayPal", self.detalles)


class PagoCripto(MetodoPago):
    def __init__(self):
        self.detalles = {}

    def iniciar_pago(self):
        dialog = QDialog()
        dialog.setWindowTitle("Pago con Criptomoneda")
        layout = QFormLayout(dialog)
        self.wallet_address = QLineEdit()
        layout.addRow("Dirección de Wallet:", self.wallet_address)
        botones = QHBoxLayout()
        boton_aceptar = QPushButton("Aceptar")
        boton_aceptar.clicked.connect(dialog.accept)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(dialog.reject)
        botones.addWidget(boton_aceptar)
        botones.addWidget(boton_cancelar)
        layout.addRow(botones)
        if dialog.exec_() == QDialog.Accepted:
            self.detalles = {
                "wallet_address": self.wallet_address.text(),
            }
            return True
        return False

    def validar_informacion(self):
        # Verificar que todos los campos tengan información
        return all(self.detalles.values())

    def procesar_pago(self):
        # Llamar al servidor para procesar el pago
        return StadiumAPI.procesar_pago("Criptomoneda", self.detalles)


class SearchControls(QWidget):
    def __init__(self, stadium_view):
        super().__init__()
        self.stadium_view = stadium_view
        self.setup_ui()
        self.reserva_id = None
        self.asientos_sugeridos = []
        self.timer = None

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # Combo para categorías
        self.categoria_combo = QComboBox()
        self.categoria_combo.addItems(["VIP", "Regular", "Sol", "Platea"])
        layout.addWidget(QLabel("Categoría:"))
        layout.addWidget(self.categoria_combo)

        # Combo para cantidad de asientos
        self.cantidad_combo = QComboBox()
        self.cantidad_combo.addItems(["1", "2", "3"])
        layout.addWidget(QLabel("Cantidad de asientos:"))
        layout.addWidget(self.cantidad_combo)

        # Combo para método de pago
        self.metodo_pago_combo = QComboBox()
        self.metodo_pago_combo.addItems(["Tarjeta", "PayPal", "Criptomoneda"])
        layout.addWidget(QLabel("Método de Pago:"))
        layout.addWidget(self.metodo_pago_combo)

        # Botón de búsqueda
        self.search_button = QPushButton("Buscar asientos")
        self.search_button.clicked.connect(self.search_seats)
        layout.addWidget(self.search_button)

        # Botón para reservar asientos
        self.reserve_button = QPushButton("Reservar")
        self.reserve_button.clicked.connect(self.reserve_seats)
        self.reserve_button.setEnabled(False)
        layout.addWidget(self.reserve_button)

        # Botón para confirmar compra
        self.confirm_button = QPushButton("Confirmar Compra")
        self.confirm_button.clicked.connect(self.confirm_purchase)
        self.confirm_button.setEnabled(False)
        layout.addWidget(self.confirm_button)

        # Botón para cancelar
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancel_purchase)
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.cancel_button)

        layout.addStretch()

    def search_seats(self):
        categoria = self.categoria_combo.currentText()
        cantidad = int(self.cantidad_combo.currentText())

        # Usar la API para buscar asientos
        result = StadiumAPI.buscar_asientos(categoria, cantidad)

        if result:
            # Encontrar los asientos en el mapa y resaltarlos
            zona = result['zona']
            categoria = result['categoria']
            asientos_encontrados = []

            for fila, columna in result['asientos']:
                seats = self.stadium_view.find_seats_in_map(zona, categoria, [(fila, columna)])
                asientos_encontrados.extend(seats)

            if asientos_encontrados:
                self.stadium_view.highlight_seats(asientos_encontrados)
                self.asientos_sugeridos = [(fila, columna) for fila, columna in result['asientos']]
                self.zona_reservada = zona
                self.categoria_reservada = categoria

                self.reserve_button.setEnabled(True)
                self.confirm_button.setEnabled(False)
                self.cancel_button.setEnabled(True)
            else:
                QMessageBox.information(self, "Información", "No se encontraron asientos disponibles.")
        else:
            QMessageBox.information(self, "Información", "No se encontraron asientos consecutivos disponibles.")

    def reserve_seats(self):
        # Reservar asientos temporalmente
        reserva = StadiumAPI.reservar_asientos_temporalmente(
            self.zona_reservada, self.categoria_reservada, self.asientos_sugeridos
        )
        if reserva and 'reserva_id' in reserva:
            self.reserva_id = reserva['reserva_id']
            self.confirm_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.reserve_button.setEnabled(False)
            self.start_timer()
        else:
            self.reserva_id = None
            self.asientos_sugeridos = []
            QMessageBox.warning(self, "Error", "No se pudieron reservar los asientos.")

    def start_timer(self):
        # Iniciar temporizador de 5 minutos
        self.timer = QTimer()
        self.timer.timeout.connect(self.expire_reservation)
        self.timer.start(300000)  # 5 minutos en milisegundos

    def expire_reservation(self):
        # Notificar al usuario que la reserva ha expirado
        QMessageBox.information(self, "Reserva expirada", "Su reserva ha expirado.")
        self.stadium_view.reset_suggested_seats()
        self.confirm_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.reserve_button.setEnabled(False)
        self.timer.stop()
        self.reserva_id = None

    def confirm_purchase(self):
        # Iniciar proceso de pago
        metodo_seleccionado = self.metodo_pago_combo.currentText()
        if metodo_seleccionado == "Tarjeta":
            metodo_pago = PagoTarjeta()
        elif metodo_seleccionado == "PayPal":
            metodo_pago = PagoPayPal()
        else:
            metodo_pago = PagoCripto()

        if metodo_pago.iniciar_pago() and metodo_pago.validar_informacion():
            pago_result = metodo_pago.procesar_pago()
            if pago_result and pago_result.get('aprobado'):
                # Confirmar compra en el servidor
                confirmacion = StadiumAPI.confirmar_compra(self.reserva_id)
                if confirmacion:
                    QMessageBox.information(self, "Compra exitosa", "Su compra ha sido confirmada.")
                    self.stadium_view.reset_suggested_seats()
                    self.confirm_button.setEnabled(False)
                    self.cancel_button.setEnabled(False)
                    self.reserve_button.setEnabled(False)
                    if self.timer:
                        self.timer.stop()
                    self.reserva_id = None
                else:
                    QMessageBox.warning(self, "Error", "No se pudo confirmar la compra.")
            else:
                QMessageBox.warning(self, "Pago rechazado", "El pago ha sido rechazado.")
        else:
            QMessageBox.warning(self, "Datos inválidos", "La información de pago es inválida.")

    def cancel_purchase(self):
        # Enviar solicitud al servidor para cancelar la reserva
        if self.reserva_id:
            cancelacion = StadiumAPI.cancelar_reserva(self.reserva_id)
            if cancelacion:
                QMessageBox.information(self, "Reserva cancelada", "La reserva ha sido cancelada.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo cancelar la reserva.")
            self.reserva_id = None

        # Restablecer los asientos sugeridos
        self.stadium_view.reset_suggested_seats()
        self.confirm_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.reserve_button.setEnabled(False)
        if self.timer:
            self.timer.stop()


class StadiumWindow(QMainWindow):
    def __init__(self, estadio):
        super().__init__()
        self.setup_window()
        self.setup_ui(estadio)

    def setup_window(self):
        self.setWindowTitle("Estructura del Estadio")
        self.setGeometry(100, 100, 1000, 800)

    def setup_ui(self, estadio):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Crear la vista del estadio
        self.stadium_view = StadiumView(estadio)

        # Agregar controles de búsqueda
        self.search_controls = SearchControls(self.stadium_view)
        layout.addWidget(self.search_controls)
        layout.addWidget(LegendWidget())
        layout.addWidget(self.stadium_view)


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
