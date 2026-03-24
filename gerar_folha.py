from PIL import Image, ImageDraw, ImageFont
import qrcode
import os
import io
import base64


def gerar_layout_prova(id_prova, qtd_questoes):
    """
    Gera a folha de respostas com QR Code
    Retorna o caminho do arquivo gerado
    """
    # Tamanho A4 em pixels
    largura = 800
    altura = 1100

    # Cria imagem branca
    img = Image.new('RGB', (largura, altura), 'white')
    draw = ImageDraw.Draw(img)

    # Tenta carregar fontes (usa padrão se não encontrar)
    try:
        # Tenta fonte do sistema
        font_titulo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_pequena = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except:
        # Fallback para fonte padrão
        font_titulo = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_pequena = ImageFont.load_default()

    # Gera QR Code
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(id_prova)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((140, 140))

    # Coloca QR Code (canto superior direito)
    img.paste(qr_img, (largura - 160, 30))

    # Cabeçalho
    draw.text((50, 50), f"PROVA: {id_prova}", fill='black', font=font_titulo)
    draw.text((50, 100), "NOME: ___________________________", fill='black', font=font_normal)
    draw.text((50, 140), "DATA: ___/___/_______", fill='black', font=font_normal)

    # Instruções
    draw.text((50, 190), "INSTRUÇÕES:", fill='black', font=font_normal)
    draw.text((50, 215), "Preencha COMPLETAMENTE o círculo da resposta correta", fill='gray', font=font_pequena)
    draw.text((50, 235), "Use caneta preta ou azul escura", fill='gray', font=font_pequena)

    # Linha divisória
    draw.line([(30, 265), (largura - 30, 265)], fill='gray', width=1)

    # Configuração das questões
    questoes_por_coluna = 20
    y_inicio = 290

    # Calcula quantas colunas serão necessárias
    if qtd_questoes <= 20:
        total_colunas = 1
        x_base_colunas = [50]
        espacamento_letras = 50
    elif qtd_questoes <= 40:
        total_colunas = 2
        x_base_colunas = [50, 430]
        espacamento_letras = 45
    else:
        total_colunas = 3
        x_base_colunas = [30, 290, 550]
        espacamento_letras = 40

    # Gera as questões
    for i in range(min(qtd_questoes, 60)):  # Limite de 60 questões
        coluna = i // questoes_por_coluna

        if coluna >= total_colunas:
            break

        linha = i % questoes_por_coluna
        x_base = x_base_colunas[coluna]
        y = y_inicio + (linha * 38)

        # Número da questão
        draw.text((x_base, y), f"{i + 1:02d}.", fill='black', font=font_normal)

        # Opções A, B, C, D, E
        for j, letra in enumerate(['A', 'B', 'C', 'D', 'E']):
            x_bolinha = x_base + 50 + (j * espacamento_letras)

            # Desenha círculo
            draw.ellipse([x_bolinha - 10, y - 8, x_bolinha + 10, y + 12], outline='black', width=1)

            # Letra dentro do círculo
            draw.text((x_bolinha - 5, y - 2), letra, fill='black', font=font_pequena)

    # Rodapé
    draw.text((50, altura - 40), "Sistema de Correção Automática de Provas", fill='gray', font=font_pequena)
    draw.text((50, altura - 20), "Escaneie o QR Code para identificação", fill='gray', font=font_pequena)

    # Salva a imagem
    caminho = os.path.join(os.path.dirname(__file__), f"folha_{id_prova}.png")
    img.save(caminho, 'PNG', quality=95)

    return caminho


def gerar_gabarito_txt(id_prova, gabarito, valor_total, qtd_questoes):
    """
    Gera arquivo de gabarito em TXT para referência
    """
    caminho = os.path.join(os.path.dirname(__file__), f"gabarito_{id_prova}.txt")

    with open(caminho, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write(f"GABARITO DA PROVA: {id_prova}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Quantidade de Questões: {qtd_questoes}\n")
        f.write(f"Valor Total: R$ {valor_total:.2f}\n")
        f.write(f"Valor por Questão: R$ {(valor_total / qtd_questoes):.2f}\n\n")
        f.write("=" * 50 + "\n")
        f.write("DETALHAMENTO DO GABARITO:\n")
        f.write("=" * 50 + "\n\n")

        for i, letra in enumerate(gabarito, 1):
            f.write(f"Questão {i:02d}: {letra}\n")

        f.write("\n" + "=" * 50 + "\n")
        f.write("INSTRUÇÕES PARA CORREÇÃO:\n")
        f.write("1. Posicione a folha de respostas do aluno na câmera\n")
        f.write("2. Certifique-se que o QR Code está visível\n")
        f.write("3. Aguarde a correção automática\n")

    return caminho