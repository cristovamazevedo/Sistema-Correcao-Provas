import cv2
import numpy as np
import sqlite3
import os
from datetime import datetime


class ProcessadorProva:
    def __init__(self):
        # Configurações para detecção do gabarito
        self.MIN_AREA_CIRCULO = 50
        self.MAX_AREA_CIRCULO = 400
        self.QUESTAO_ALTURA = 38
        self.INICIO_GABARITO_Y = 280
        self.LARGURA_COLUNA = 250
        self.OFFSET_LETRAS = 40
        self.LETRAS = ['A', 'B', 'C', 'D', 'E']

    def detectar_regiao_gabarito(self, imagem):
        """
        Detecta automaticamente a região do gabarito baseado no QR Code
        Retorna: (regiao_gabarito, coordenadas_bbox)
        """
        try:
            # Converte para escala de cinza
            gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

            # Detecta QR Code
            qr_detector = cv2.QRCodeDetector()
            data, bbox, _ = qr_detector.detectAndDecode(gray)

            if bbox is not None and len(bbox) > 0:
                # Pega os pontos do QR Code
                pts = bbox[0].astype(np.int32)
                x_qr = min(pts[:, 0])
                y_qr = min(pts[:, 1])
                w_qr = max(pts[:, 0]) - x_qr
                h_qr = max(pts[:, 1]) - y_qr

                # Define a região do gabarito (abaixo do QR Code)
                x_gab = max(0, x_qr - 30)
                y_gab = y_qr + h_qr + 20
                w_gab = min(imagem.shape[1] - x_gab, w_qr + 500)
                h_gab = 500  # Altura suficiente para o gabarito

                if y_gab + h_gab <= imagem.shape[0]:
                    regiao_gabarito = imagem[y_gab:y_gab + h_gab, x_gab:x_gab + w_gab]
                    return regiao_gabarito, (x_gab, y_gab, w_gab, h_gab), data

            # Fallback: usa a parte inferior da imagem
            altura = imagem.shape[0]
            regiao = imagem[int(altura * 0.4):, :]
            return regiao, (0, int(altura * 0.4), imagem.shape[1], int(altura * 0.6)), data

        except Exception as e:
            print(f"Erro ao detectar região: {e}")
            return imagem, None, None

    def processar_gabarito(self, imagem, qtd_questoes_max=100):
        """
        Processa a imagem do gabarito e retorna as respostas detectadas
        """
        try:
            # Converte para escala de cinza
            if len(imagem.shape) == 3:
                gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
            else:
                gray = imagem

            # Melhora o contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

            # Threshold adaptativo
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY_INV, 11, 2)

            # Remove ruído
            kernel = np.ones((2, 2), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

            # Encontra contornos
            contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            respostas = {}

            for contorno in contornos:
                area = cv2.contourArea(contorno)

                if self.MIN_AREA_CIRCULO < area < self.MAX_AREA_CIRCULO:
                    # Calcula o centro
                    M = cv2.moments(contorno)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])

                        # Identifica questão e letra
                        questao = self.identificar_questao(cy, imagem.shape[0])
                        letra = self.identificar_letra(cx, imagem.shape[1])

                        if questao and letra and questao <= qtd_questoes_max:
                            # Se já tem resposta, mantém a com maior área
                            if questao in respostas:
                                if area > respostas[questao][1]:
                                    respostas[questao] = (letra, area)
                            else:
                                respostas[questao] = (letra, area)

            # Converte para formato simples
            return {q: l for q, (l, _) in respostas.items()}

        except Exception as e:
            print(f"Erro ao processar gabarito: {e}")
            return {}

    def identificar_questao(self, y, altura_imagem):
        """Identifica o número da questão baseado na coordenada Y"""
        if y < self.INICIO_GABARITO_Y:
            return None

        questao = (y - self.INICIO_GABARITO_Y) // self.QUESTAO_ALTURA
        return int(questao) + 1 if 0 <= questao <= 100 else None

    def identificar_letra(self, x, largura_imagem):
        """Identifica a letra baseado na coordenada X"""
        coluna = int(x // self.LARGURA_COLUNA)
        x_dentro_coluna = x - (coluna * self.LARGURA_COLUNA + 75)
        idx_letra = int(x_dentro_coluna / self.OFFSET_LETRAS)

        if 0 <= idx_letra < len(self.LETRAS):
            return self.LETRAS[idx_letra]
        return None

    def calcular_nota_com_erros(self, respostas, gabarito_correto, valor_total):
        """
        Calcula a nota e retorna os erros detalhados
        """
        qtd_questoes = len(gabarito_correto)
        acertos = 0
        erros = {}

        for i in range(qtd_questoes):
            questao = i + 1
            resposta_aluno = respostas.get(questao)
            resposta_correta = gabarito_correto[i] if i < len(gabarito_correto) else None

            if resposta_aluno and resposta_correta:
                if resposta_aluno == resposta_correta:
                    acertos += 1
                    erros[questao] = {
                        'status': 'acertou',
                        'aluno': resposta_aluno,
                        'correta': resposta_correta
                    }
                else:
                    erros[questao] = {
                        'status': 'errou',
                        'aluno': resposta_aluno,
                        'correta': resposta_correta
                    }
            elif resposta_aluno and not resposta_correta:
                erros[questao] = {
                    'status': 'invalido',
                    'aluno': resposta_aluno,
                    'correta': 'N/A'
                }
            else:
                erros[questao] = {
                    'status': 'nao_respondeu',
                    'aluno': None,
                    'correta': resposta_correta
                }

        nota = (acertos / qtd_questoes) * valor_total if qtd_questoes > 0 else 0
        return round(nota, 2), acertos, erros

    def marcar_erros_na_imagem(self, imagem_original, erros, bbox_gabarito, gabarito_correto):
        """
        Marca os erros na imagem com X vermelhos e círculos verdes nas respostas corretas
        """
        imagem_marcada = imagem_original.copy()

        # Desenha retângulo ao redor da região do gabarito
        if bbox_gabarito:
            x, y, w, h = bbox_gabarito
            cv2.rectangle(imagem_marcada, (x, y), (x + w, y + h), (0, 255, 0), 3)

        # Para cada questão com erro, marca na imagem
        for questao, info in erros.items():
            if info['status'] == 'errou':
                # Calcula posição Y da questão
                y_pos = self.INICIO_GABARITO_Y + (questao - 1) * self.QUESTAO_ALTURA

                # Calcula posição X baseado na coluna
                coluna = (questao - 1) // 20
                x_base = 30 + (coluna * self.LARGURA_COLUNA)

                # Adiciona offset do gabarito se disponível
                if bbox_gabarito:
                    x_base += bbox_gabarito[0]
                    y_pos += bbox_gabarito[1]

                # Desenha X vermelho no erro
                cv2.putText(imagem_marcada, "X", (x_base, y_pos + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                # Desenha círculo verde na resposta correta
                if info['correta'] and info['correta'] in self.LETRAS:
                    idx_letra = self.LETRAS.index(info['correta'])
                    x_correta = x_base + 45 + (idx_letra * self.OFFSET_LETRAS)
                    cv2.circle(imagem_marcada, (x_correta, y_pos), 14, (0, 255, 0), 2)

        return imagem_marcada


# Função principal para compatibilidade
def alinhar_e_corrigir(caminho_foto):
    """
    Função principal de correção
    Retorna: (nota, id_prova, erros_detalhados, imagem_marcada)
    """
    processador = ProcessadorProva()

    try:
        # Carrega a imagem
        imagem = cv2.imread(caminho_foto)
        if imagem is None:
            return None, "Erro ao carregar imagem", None, None

        # Redimensiona se muito grande (economiza memória)
        altura, largura = imagem.shape[:2]
        if largura > 1200:
            escala = 1200 / largura
            nova_largura = 1200
            nova_altura = int(altura * escala)
            imagem = cv2.resize(imagem, (nova_largura, nova_altura))

        # Detecta região do gabarito e QR Code
        regiao_gabarito, bbox_gabarito, id_prova = processador.detectar_regiao_gabarito(imagem)

        if not id_prova:
            return None, "QR Code não detectado. Posicione a folha corretamente.", None, None

        # Busca a prova no banco de dados
        conn = sqlite3.connect('sistema.db')
        cursor = conn.cursor()
        cursor.execute("SELECT gabarito, qtd_questoes, valor_total FROM provas WHERE id_prova = ?", (id_prova,))
        resultado = cursor.fetchone()
        conn.close()

        if not resultado:
            return None, f"Prova {id_prova} não cadastrada no sistema", None, None

        gabarito_correto, qtd_questoes, valor_total = resultado
        gabarito_correto = gabarito_correto.upper()

        # Processa o gabarito
        respostas = processador.processar_gabarito(regiao_gabarito, qtd_questoes)

        # Calcula nota e erros
        nota, acertos, erros = processador.calcular_nota_com_erros(respostas, gabarito_correto, valor_total)

        # Marca erros na imagem
        imagem_marcada = processador.marcar_erros_na_imagem(imagem, erros, bbox_gabarito, gabarito_correto)

        # Salva imagem marcada
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        caminho_marcado = os.path.join(os.path.dirname(caminho_foto), f"marcada_{timestamp}.jpg")
        cv2.imwrite(caminho_marcado, imagem_marcada)

        return nota, id_prova, erros, caminho_marcado

    except Exception as e:
        print(f"Erro no processamento: {e}")
        return None, f"Erro: {str(e)}", None, None