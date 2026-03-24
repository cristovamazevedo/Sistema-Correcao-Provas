import sys
import os

# Garante que o Python encontre os arquivos na pasta atual
caminho_projeto = os.path.dirname(os.path.abspath(__file__))
if caminho_projeto not in sys.path:
    sys.path.append(caminho_projeto)

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import datetime
import qrcode
import cv2
import numpy as np
import io
import base64

# Importa o processador atualizado
from processador import alinhar_e_corrigir


def init_db():
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS provas (
            id_prova TEXT PRIMARY KEY,
            qtd_questoes INTEGER,
            valor_total REAL,
            gabarito TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()

app = Flask(__name__)
CORS(app)  # Habilita CORS para testes com celular

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def gerar_layout_prova(id_p, qtd):
    """Gera a folha de respostas com QR Code"""
    largura_a4 = 800
    altura_a4 = 1100
    folha = np.ones((altura_a4, largura_a4, 3), dtype=np.uint8) * 255
    cv2.rectangle(folha, (10, 10), (largura_a4 - 10, altura_a4 - 10), (0, 0, 0), 2)

    # QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(id_p)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img_qr = cv2.cvtColor(np.array(img_qr), cv2.COLOR_RGB2BGR)
    img_qr = cv2.resize(img_qr, (150, 150))
    folha[50:200, 600:750] = img_qr

    # Cabeçalho
    cv2.putText(folha, f"PROVA: {id_p}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    cv2.putText(folha, "NOME: ___________________________", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(folha, "Instruções: Preencha COMPLETAMENTE o círculo", (50, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (100, 100, 100), 1)

    # Questões
    questoes_por_coluna = 20
    for i in range(qtd):
        coluna = i // 20
        linha = i % 20
        x_base = 30 + (coluna * 250)
        y = 280 + (linha * 38)

        cv2.putText(folha, f"{i + 1:02d}:", (x_base, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        for j, letra in enumerate(['A', 'B', 'C', 'D', 'E']):
            distancia_letras = 40
            x_bolinha = x_base + 45 + (j * distancia_letras)
            cv2.circle(folha, (x_bolinha, y), 12, (0, 0, 0), 2)
            cv2.putText(folha, letra, (x_bolinha - 5, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 2)

    nome_arquivo = f"folha_{id_p}.png"
    caminho_completo = os.path.join(BASE_DIR, nome_arquivo)
    cv2.imwrite(caminho_completo, folha)
    return caminho_completo


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    caminho_foto = None
    try:
        if 'foto' not in request.files:
            return jsonify({"error": "Nenhuma foto enviada"}), 400

        arquivo = request.files['foto']

        if not os.path.exists("uploads"):
            os.makedirs("uploads")

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        caminho_foto = os.path.join("uploads", f"temp_{timestamp}.jpg")
        arquivo.save(caminho_foto)

        # Processa a imagem - AGORA RETORNA 4 VALORES
        resultado = alinhar_e_corrigir(caminho_foto)

        # Desempacota o resultado
        if len(resultado) == 4:
            nota, id_prova, erros, caminho_marcado = resultado
        else:
            nota, id_prova = resultado[0], resultado[1]
            erros, caminho_marcado = None, None

        if nota is None:
            return jsonify({"error": id_prova}), 400

        # Converte imagem marcada para base64 se existir
        imagem_marcada_base64 = None
        if caminho_marcado and os.path.exists(caminho_marcado):
            with open(caminho_marcado, 'rb') as f:
                imagem_marcada_base64 = base64.b64encode(f.read()).decode('utf-8')
            os.remove(caminho_marcado)

        # Salva no CSV
        try:
            arquivo_csv = "relatorio_notas.csv"
            existe = os.path.exists(arquivo_csv)

            with open(arquivo_csv, "a", encoding="utf-8") as f:
                if not existe:
                    f.write("Data/Hora,ID da Prova,Nota,Acertos,Erros\n")

                agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                acertos = sum(1 for e in erros.values() if e.get('status') == 'acertou') if erros else 0
                f.write(f"{agora},{id_prova},{nota},{acertos},{str(erros)[:200]}\n")
        except Exception as e_csv:
            print(f"Aviso: Erro ao gravar no CSV: {e_csv}")

        # Retorna com os erros e imagem marcada
        return jsonify({
            "nota": nota,
            "prova_id": id_prova,
            "erros": erros,
            "imagem_marcada": imagem_marcada_base64
        })

    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

    finally:
        if caminho_foto and os.path.exists(caminho_foto):
            try:
                os.remove(caminho_foto)
            except Exception as e_del:
                print(f"Erro ao remover arquivo: {e_del}")


@app.route('/gerar_folha', methods=['POST'])
def rota_gerar_folha():
    try:
        dados = request.get_json()
        id_p = str(dados.get('id_prova', 'PROVA')).strip()
        qtd = int(dados.get('qtd_questoes', 0))
        gabarito = str(dados.get('gabarito', '')).upper()
        valor = float(dados.get('valor_total', 10.0))

        if not id_p or qtd <= 0 or not gabarito:
            return jsonify({"error": "Dados incompletos"}), 400

        # Salva gabarito no banco - CORRIGIDO
        conn = sqlite3.connect('sistema.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO provas (id_prova, qtd_questoes, valor_total, gabarito) 
            VALUES (?, ?, ?, ?)
        """, (id_p, qtd, valor, gabarito))
        conn.commit()
        conn.close()

        # Salva arquivo TXT
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_txt = os.path.join(diretorio_atual, f"{id_p}.txt")
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(f"{gabarito},{valor}")

        # Gera a imagem
        caminho_img = gerar_layout_prova(id_p, qtd)

        if os.path.exists(caminho_img):
            return_data = io.BytesIO()
            with open(caminho_img, 'rb') as f:
                return_data.write(f.read())
            return_data.seek(0)
            os.remove(caminho_img)

            return send_file(
                return_data,
                mimetype='image/png',
                as_attachment=True,
                download_name=f"folha_{id_p}.png"
            )
        else:
            return jsonify({"error": "Arquivo de imagem não foi criado"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/baixar_relatorio')
def baixar_relatorio():
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relatorio_notas.csv")
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    return "Nenhuma nota registrada ainda.", 404


@app.route('/baixar_gabarito/<id_prova>')
def baixar_gabarito(id_prova):
    nome_arquivo = f"{id_prova.strip()}.txt"
    diretorio_base = os.path.dirname(os.path.abspath(__file__))
    caminho_completo = os.path.join(diretorio_base, nome_arquivo)

    if os.path.exists(caminho_completo):
        return send_file(caminho_completo, as_attachment=True)
    else:
        return f"Erro: O arquivo {nome_arquivo} não foi encontrado.", 400


@app.route('/listar_provas', methods=['GET'])
def listar_provas():
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id_prova, qtd_questoes, valor_total, gabarito FROM provas ORDER BY rowid DESC")
    provas = cursor.fetchall()
    conn.close()

    return jsonify({
        'provas': [{
            'id': p[0],
            'qtd_questoes': p[1],
            'valor_total': p[2],
            'gabarito': p[3][:30] + ('...' if len(p[3]) > 30 else '')
        } for p in provas]
    })


@app.route('/marcar_gabarito/<id_prova>')
def marcar_gabarito(id_prova):
    """Página para marcar o gabarito visualmente"""
    return render_template('marcar_gabarito.html', id_prova=id_prova)


@app.route('/api/salvar_gabarito_visual', methods=['POST'])
def salvar_gabarito_visual():
    """Salva o gabarito marcado visualmente"""
    try:
        dados = request.json
        id_prova = dados.get('id_prova', '').strip().upper()
        qtd_questoes = int(dados.get('qtd_questoes', 0))
        valor_total = float(dados.get('valor_total', 10.0))
        gabarito = dados.get('gabarito', '').upper().strip()

        if not id_prova or qtd_questoes <= 0 or not gabarito:
            return jsonify({'error': 'Dados incompletos'}), 400

        if len(gabarito) != qtd_questoes:
            return jsonify({'error': f'Gabarito deve ter {qtd_questoes} questões'}), 400

        # Salva no banco - CORRIGIDO
        conn = sqlite3.connect('sistema.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO provas (id_prova, qtd_questoes, valor_total, gabarito) 
            VALUES (?, ?, ?, ?)
        """, (id_prova, qtd_questoes, valor_total, gabarito))
        conn.commit()
        conn.close()

        # Salva arquivo TXT
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_txt = os.path.join(diretorio_atual, f"{id_prova}.txt")
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(f"{gabarito},{valor_total}")

        return jsonify({
            'success': True,
            'message': 'Gabarito salvo com sucesso!',
            'id_prova': id_prova
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/folha/<id_prova>')
def download_folha(id_prova):
    """Baixa a folha de respostas gerada"""
    try:
        conn = sqlite3.connect('sistema.db')
        cursor = conn.cursor()
        cursor.execute("SELECT qtd_questoes FROM provas WHERE id_prova = ?", (id_prova,))
        resultado = cursor.fetchone()
        conn.close()

        if not resultado:
            return jsonify({'error': 'Prova não encontrada'}), 404

        qtd_questoes = resultado[0]

        # Gera a folha
        caminho = gerar_layout_prova(id_prova, qtd_questoes)

        # Envia o arquivo
        with open(caminho, 'rb') as f:
            data = f.read()

        # Remove o arquivo temporário
        os.remove(caminho)

        return send_file(
            io.BytesIO(data),
            mimetype='image/png',
            as_attachment=True,
            download_name=f'folha_{id_prova}.png'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/prova/<id_prova>', methods=['GET'])
def get_prova(id_prova):
    """Retorna os dados de uma prova específica"""
    conn = sqlite3.connect('sistema.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id_prova, qtd_questoes, valor_total, gabarito FROM provas WHERE id_prova = ?", (id_prova,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({
            'id_prova': row[0],
            'qtd_questoes': row[1],
            'valor_total': row[2],
            'gabarito': row[3]
        })
    return jsonify({'error': 'Prova não encontrada'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)