import sqlite3
import json
import os
from datetime import datetime, timedelta


class Database:
    def __init__(self):
        # Usa caminho absoluto do PythonAnywhere
        self.db_path = os.path.join(os.path.dirname(__file__), 'sistema.db')
        self.init_db()
        self.verificar_e_limpar_espaco()

    def get_db_size_mb(self):
        """Retorna tamanho do banco em MB"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path) / (1024 * 1024)
        return 0

    def verificar_e_limpar_espaco(self):
        """Verifica espaço e limpa se necessário"""
        tamanho = self.get_db_size_mb()

        # Se banco > 45MB, faz limpeza agressiva
        if tamanho > 45:
            self.limpeza_agressiva()
        # Se > 30MB, limpeza moderada
        elif tamanho > 30:
            self.limpeza_moderada()

    def limpeza_agressiva(self):
        """Limpeza agressiva para liberar espaço"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Mantém apenas últimas 100 correções
            cursor.execute("""
                DELETE FROM correcoes 
                WHERE id NOT IN (
                    SELECT id FROM correcoes 
                    ORDER BY data_correcao DESC 
                    LIMIT 100
                )
            """)

            # Remove provas antigas sem correções
            cursor.execute("""
                DELETE FROM provas 
                WHERE id_prova NOT IN (
                    SELECT DISTINCT id_prova FROM correcoes
                )
            """)

            conn.commit()

            # Vacuum para compactar
            cursor.execute("VACUUM")
            conn.commit()
            conn.close()

            print(f"Limpeza agressiva realizada. Banco agora: {self.get_db_size_mb():.2f}MB")

        except Exception as e:
            print(f"Erro na limpeza agressiva: {e}")

    def limpeza_moderada(self):
        """Limpeza moderada"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Remove correções com mais de 60 dias
            data_limite = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("DELETE FROM correcoes WHERE data_correcao < ?", (data_limite,))

            conn.commit()
            conn.close()

            print(f"Limpeza moderada realizada. Banco agora: {self.get_db_size_mb():.2f}MB")

        except Exception as e:
            print(f"Erro na limpeza moderada: {e}")

    def init_db(self):
        """Inicializa banco de dados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabela de provas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS provas (
                id_prova TEXT PRIMARY KEY,
                qtd_questoes INTEGER,
                valor_total REAL,
                gabarito TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de correções (compactada)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correcoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_prova TEXT,
                nota REAL,
                acertos INTEGER,
                erros TEXT,
                data_correcao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_prova) REFERENCES provas (id_prova)
            )
        ''')

        # Tabela de controle de espaço
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS controle_espaco (
                chave TEXT PRIMARY KEY,
                valor TEXT,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def salvar_prova(self, id_prova, qtd_questoes, valor_total, gabarito):
        """Salva prova (apenas texto)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO provas (id_prova, qtd_questoes, valor_total, gabarito)
            VALUES (?, ?, ?, ?)
        """, (id_prova, qtd_questoes, valor_total, gabarito))
        conn.commit()
        conn.close()

        # Verifica espaço após salvar
        self.verificar_e_limpar_espaco()

    def buscar_prova(self, id_prova):
        """Busca prova"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_prova, qtd_questoes, valor_total, gabarito
            FROM provas WHERE id_prova = ?
        """, (id_prova,))
        resultado = cursor.fetchone()
        conn.close()

        if resultado:
            return {
                'id_prova': resultado[0],
                'qtd_questoes': resultado[1],
                'valor_total': resultado[2],
                'gabarito': resultado[3]
            }
        return None

    def salvar_correcao(self, id_prova, nota, acertos, erros):
        """Salva correção com compactação"""
        # Verifica limite de correções
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Conta correções atuais
        cursor.execute("SELECT COUNT(*) FROM correcoes")
        total_correcoes = cursor.fetchone()[0]

        # Se excedeu limite, remove as mais antigas
        if total_correcoes >= 500:  # Limite de 500 correções
            cursor.execute("""
                DELETE FROM correcoes 
                WHERE id IN (
                    SELECT id FROM correcoes 
                    ORDER BY data_correcao ASC 
                    LIMIT ?
                )
            """, (total_correcoes - 400,))  # Mantém 400, remove o excesso

        # Compacta erros (remove dados desnecessários)
        erros_compactados = {}
        for questao, info in erros.items():
            erros_compactados[questao] = {
                's': info['status'][0],  # 'a'=acertou, 'e'=errou, 'n'=não respondeu
                'a': info.get('aluno', ''),
                'c': info.get('correta', '')
            }

        erros_json = json.dumps(erros_compactados, ensure_ascii=False, separators=(',', ':'))

        cursor.execute("""
            INSERT INTO correcoes (id_prova, nota, acertos, erros)
            VALUES (?, ?, ?, ?)
        """, (id_prova, nota, acertos, erros_json))

        conn.commit()
        conn.close()

        # Verifica espaço após salvar
        self.verificar_e_limpar_espaco()

    def listar_correcoes(self, id_prova=None, limit=200):
        """Lista correções com limite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if id_prova:
            cursor.execute("""
                SELECT * FROM correcoes 
                WHERE id_prova = ? 
                ORDER BY data_correcao DESC 
                LIMIT ?
            """, (id_prova, limit))
        else:
            cursor.execute("""
                SELECT * FROM correcoes 
                ORDER BY data_correcao DESC 
                LIMIT ?
            """, (limit,))

        resultados = cursor.fetchall()
        conn.close()

        correcoes = []
        for row in resultados:
            try:
                erros_raw = json.loads(row[4])
                # Descompacta erros
                erros = {}
                for q, info in erros_raw.items():
                    status_map = {'a': 'acertou', 'e': 'errou', 'n': 'nao_respondeu'}
                    erros[int(q)] = {
                        'status': status_map.get(info['s'], 'nao_respondeu'),
                        'aluno': info['a'] if info['a'] else None,
                        'correta': info['c']
                    }
            except:
                erros = {}

            correcoes.append({
                'id': row[0],
                'id_prova': row[1],
                'nota': row[2],
                'acertos': row[3],
                'erros': erros,
                'data_correcao': row[5]
            })

        return correcoes

    def listar_provas(self, limit=100):
        """Lista provas com limite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM provas 
            ORDER BY data_criacao DESC 
            LIMIT ?
        """, (limit,))
        resultados = cursor.fetchall()
        conn.close()

        provas = []
        for row in resultados:
            provas.append({
                'id_prova': row[0],
                'qtd_questoes': row[1],
                'valor_total': row[2],
                'gabarito': row[3][:50] + ('...' if len(row[3]) > 50 else ''),
                'gabarito_completo': row[3],
                'data_criacao': row[4]
            })

        return provas

    def get_estatisticas(self):
        """Estatísticas básicas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM correcoes")
        total_correcoes = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(nota) FROM correcoes")
        media_notas = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(DISTINCT id_prova) FROM correcoes")
        total_provas = cursor.fetchone()[0]

        tamanho_db = self.get_db_size_mb()

        conn.close()

        return {
            'total_correcoes': total_correcoes,
            'media_notas': round(media_notas, 2),
            'total_provas_distintas': total_provas,
            'tamanho_banco_mb': round(tamanho_db, 2)
        }

    def exportar_relatorio_csv(self):
        """Exporta relatório em CSV sem armazenar"""
        correcoes = self.listar_correcoes(limit=500)

        import io
        output = io.StringIO()
        output.write("ID,Data,ID Prova,Nota,Acertos,Total Questões,Detalhes\n")

        for c in correcoes:
            total = len(c['erros'])
            detalhes = []
            for q, info in c['erros'].items():
                detalhes.append(f"Q{q}:{info['status'][0]}")

            output.write(
                f"{c['id']},{c['data_correcao']},{c['id_prova']},{c['nota']},{c['acertos']},{total},\"{';'.join(detalhes[:20])}\"\n")

        return output.getvalue()

    def limpar_tudo(self):
        """Limpa todo o banco (uso emergencial)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM correcoes")
            cursor.execute("DELETE FROM provas")
            cursor.execute("VACUUM")

            conn.commit()
            conn.close()

            return True
        except:
            return False