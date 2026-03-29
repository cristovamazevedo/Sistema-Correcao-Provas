import cv2
import numpy as np
import sqlite3
import os
from datetime import datetime

class ProcessadorProva:
    def __init__(self):
        self.MIN_AREA_CIRCULO = 50
        self.MAX_AREA_CIRCULO = 400
        self.QUESTAO_ALTURA = 38
        self.INICIO_GABARITO_Y = 280
        self.LARGURA_COLUNA = 250
        self.OFFSET_LETRAS = 40
        self.LETRAS = ['A', 'B', 'C', 'D', 'E']

    def detectar_regiao_gabarito(self, imagem):
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
        qr_detector = cv2.QRCodeDetector()
        data, bbox, _ = qr_detector.detectAndDecode(gray)
        if bbox is not None and len(bbox) > 0:
            pts = bbox[0].astype(np.int32)
            x_qr = min(pts[:, 0]); y_qr = min(pts[:, 1]); w_qr = max(pts[:, 0]) - x_qr; h_qr = max(pts[:, 1]) - y_qr
            x_gab = max(0, x_qr - 30); y_gab = y_qr + h_qr + 20
            w_gab = min(imagem.shape[1] - x_gab, w_qr + 500); h_gab = 500
            if y_gab + h_gab <= imagem.shape[0]:
                regiao_gabarito = imagem[y_gab:y_gab + h_gab, x_gab:x_gab + w_gab]
                return regiao_gabarito, (x_gab, y_gab, w_gab, h_gab), data
        altura = imagem.shape[0]
        regiao = imagem[int(altura * 0.4):, :]
        return regiao, (0, int(altura * 0.4), imagem.shape[1], int(altura * 0.6)), data

    def processar_gabarito(self, imagem, qtd_questoes_max=100):
        if len(imagem.shape) == 3:
            gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
        else:
            gray = imagem
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        respostas = {}
        for contorno in contornos:
            area = cv2.contourArea(contorno)
            if self.MIN_AREA_CIRCULO < area < self.MAX_AREA_CIRCULO:
                M = cv2.moments(contorno)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    questao = self.identificar_questao(cy, imagem.shape[0])
                    letra = self.identificar_letra(cx, imagem.shape[1])
                    if questao and letra and questao <= qtd_questoes_max:
                        if questao in respostas:
                            if area > respostas[questao][1]:
                                respostas[questao] = (letra, area)
                        else:
                            respostas[questao] = (letra, area)
        return {q: l for q, (l, _) in respostas.items()}

    def identificar_questao(self, y, altura_imagem):
        if y < self.INICIO_GABARITO_Y:
            return None
        questao = (y - self.INICIO_GABARITO_Y) // self.QUESTAO_ALTURA
        return int(questao) + 1 if 0 <= questao <= 100 else None

    def identificar_letra(self, x, largura_imagem):
        coluna = int(x // self.LARGURA_COLUNA)
        x_dentro_coluna = x - (coluna * self.LARGURA_COLUNA + 75)
        idx_letra = int(x_dentro_coluna / self.OFFSET_LETRAS)
        if 0 <= idx_letra < len(self.LETRAS):
            return self.LETRAS[idx_letra]
        return None

    def calcular_nota_com_erros(self, respostas, gabarito_correto, valor_total):
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
                    erros[questao] = {'status': 'acertou', 'aluno': resposta_aluno, 'correta': resposta_correta}
                else:
                    erros[questao] = {'status': 'errou', 'aluno': resposta_aluno, 'correta': resposta_correta}
            elif resposta_aluno and not resposta_correta:
                erros[questao] = {'status': 'invalido', 'aluno': resposta_aluno, 'correta': 'N/A'}
            else:
                erros[questao] = {'status': 'nao_respondeu', 'aluno': None, 'correta': resposta_correta}
        nota = (acertos / qtd_questoes) * valor_total if qtd_questoes > 0 else 0
        return round(nota, 2), acertos, erros

    def marcar_erros_na_imagem(self, imagem_original, erros, bbox_gabarito, gabarito_correto, respostas_detectadas):
        imagem_marcada = imagem_original.copy()
        if bbox_gabarito:
            x, y, w, h = bbox_gabarito
            cv2.rectangle(imagem_marcada, (x, y), (x + w, y + h), (0, 255, 0), 3)

        # Desenha círculos amarelos para todas as respostas detectadas
        for questao, letra in respostas_detectadas.items():
            y_pos = self.INICIO_GABARITO_Y + (questao - 1) * self.QUESTAO_ALTURA
            coluna = (questao - 1) // 20
            x_base = 30 + (coluna * self.LARGURA_COLUNA)
            if letra in self.LETRAS:
                idx_letra = self.LETRAS.index(letra)
                x_bolinha = x_base + 45 + (idx_letra * self.OFFSET_LETRAS)
                if bbox_gabarito:
                    x_bolinha += bbox_gabarito[0]
                    y_pos += bbox_gabarito[1]
                cv2.circle(imagem_marcada, (x_bolinha, y_pos), 14, (0, 255, 255), 2)  # amarelo

        # Marca os erros com X vermelho e círculo verde para a resposta correta
        for questao, info in erros.items():
            y_pos = self.INICIO_GABARITO_Y + (questao - 1) * self.QUESTAO_ALTURA
            coluna = (questao - 1) // 20
            x_base = 30 + (coluna * self.LARGURA_COLUNA)
            if bbox_gabarito:
                x_base += bbox_gabarito[0]
                y_pos += bbox_gabarito[1]
            if info['status'] == 'errou':
                cv2.putText(imagem_marcada, "X", (x_base, y_pos + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                if info['correta'] and info['correta'] in self.LETRAS:
                    idx_letra = self.LETRAS.index(info['correta'])
                    x_correta = x_base + 45 + (idx_letra * self.OFFSET_LETRAS)
                    cv2.circle(imagem_marcada, (x_correta, y_pos), 14, (0, 255, 0), 2)
        return imagem_marcada


# Função principal de compatibilidade
def alinhar_e_corrigir(caminho_foto):
    processador = ProcessadorProva()
    try:
        imagem = cv2.imread(caminho_foto)
        if imagem is None:
            return None, "Erro ao carregar imagem", None, None
        altura, largura = imagem.shape[:2]
        if largura > 1200:
            escala = 1200 / largura
            nova_largura = 1200
            nova_altura = int(altura * escala)
            imagem = cv2.resize(imagem, (nova_largura, nova_altura))

        regiao_gabarito, bbox_gabarito, id_prova = processador.detectar_regiao_gabarito(imagem)
        if not id_prova:
            return None, "QR Code não detectado. Posicione a folha corretamente.", None, None

        conn = sqlite3.connect('sistema.db')
        cursor = conn.cursor()
        cursor.execute("SELECT gabarito, qtd_questoes, valor_total FROM provas WHERE id_prova = ?", (id_prova,))
        resultado = cursor.fetchone()
        conn.close()
        if not resultado:
            return None, f"Prova {id_prova} não cadastrada", None, None

        gabarito_correto, qtd_questoes, valor_total = resultado
        gabarito_correto = gabarito_correto.upper()
        respostas = processador.processar_gabarito(regiao_gabarito, qtd_questoes)
        nota, acertos, erros = processador.calcular_nota_com_erros(respostas, gabarito_correto, valor_total)

        # Marca os erros e também as respostas detectadas (amarelo)
        imagem_marcada = processador.marcar_erros_na_imagem(imagem, erros, bbox_gabarito, gabarito_correto, respostas)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        caminho_marcado = os.path.join(os.path.dirname(caminho_foto), f"marcada_{timestamp}.jpg")
        cv2.imwrite(caminho_marcado, imagem_marcada)

        return nota, id_prova, erros, caminho_marcado
    except Exception as e:
        print(f"Erro: {e}")
        return None, str(e), None, None