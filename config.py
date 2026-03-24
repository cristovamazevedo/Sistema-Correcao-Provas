import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-12345'

    # Diretórios
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # Limites de espaço (em MB)
    MAX_DB_SIZE_MB = 50  # Banco máximo 50MB
    MAX_UPLOAD_MB = 5  # Upload máximo 5MB
    MAX_CORRECOES = 500  # Máximo de correções armazenadas

    # Configurações da prova
    QUESTAO_ALTURA = 38
    INICIO_GABARITO_Y = 280
    LARGURA_COLUNA = 250
    OFFSET_LETRAS = 40
    LETRAS = ['A', 'B', 'C', 'D', 'E']

    # QR Code
    QR_SIZE = 150
    QR_POS_X = 600
    QR_POS_Y = 50

    # Processamento
    MIN_AREA_CIRCULO = 50
    MAX_AREA_CIRCULO = 400

    @staticmethod
    def init_dirs():
        """Cria diretórios necessários"""
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)