import base64
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import webview
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from mutagen import File
from mutagen.flac import Picture
from werkzeug.serving import make_server

app = Flask(__name__)


def obter_pasta_musicas():
    home = os.path.expanduser("~")

    # 1. Padrão XDG (funciona em qualquer idioma). Se a pasta não estiver
    #    configurada, o xdg-user-dir devolve a própria home: ignoramos isso
    #    para não varrer o disco inteiro do usuário.
    try:
        resultado = subprocess.check_output(
            ['xdg-user-dir', 'MUSIC'], text=True, timeout=3
        ).strip()
        if (
            resultado
            and os.path.isdir(resultado)
            and os.path.abspath(resultado) != os.path.abspath(home)
        ):
            return resultado
    except Exception:
        pass

    # 2. Fallback: nomes comuns de pasta na home
    for nome in ("Músicas", "Música", "Music", "Musica"):
        caminho = os.path.join(home, nome)
        if os.path.isdir(caminho):
            return caminho

    # 3. Padrão final
    return os.path.join(home, "Músicas")


PASTA_MUSICAS = obter_pasta_musicas()
EXTENSOES_VALIDAS = ('.mp3', '.wav', '.ogg', '.oga', '.opus', '.flac', '.m4a', '.aac')

# Onde ficam as playlists e as preferências (sobrevive entre execuções)
PASTA_CONFIG = os.path.join(
    os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config'),
    'inert',
)
ARQUIVO_APISET = os.path.join(
    PASTA_CONFIG if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)),
    'apiset.txt',
)
ARQUIVO_ESTADO = os.path.join(PASTA_CONFIG, 'estado.json')
ORDENACOES = ('nome', 'ano', 'modificacao')
LAYOUT_PADRAO = {'lista': 340, 'playlists': 210, 'player': 310}
LIMITES_LAYOUT = {'lista': (280, 560), 'playlists': (170, 520), 'player': (270, 600)}
TEMA_PADRAO = {
    'matiz': 349,
    'acromatico': 'cor',
    'transparente': False,
    'opacidade': 70,
    'tingir': True,
    'luz': True,
}

# A janela é criada transparente; o menu Personalizar só controla quanto do fundo aparece.
# Se a janela ficar preta (sistema sem compositor/transparência), troque para False.
JANELA_TRANSPARENTE = True
TAMANHO_JANELA_PADRAO = (1240, 720)

_trava_estado = threading.Lock()

# Capa padrão (vinho e preto) para músicas sem imagem embutida.
# O xmlns precisa ser exatamente http://www.w3.org/2000/svg,
# senão o navegador não renderiza o SVG quando ele é usado em <img>.
CAPA_PADRAO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
  <path d="M185 85v95.5c-5.5-3.5-12-5.5-19-5.5-19.3 0-35 13.4-35 30s15.7 30 35 30 35-13.4 35-30V115h35V85h-51z" fill="#ffffff" fill-opacity="0.22"/>
</svg>'''


def caminho_seguro(relativo):
    """Resolve um caminho dentro da pasta de músicas e bloqueia '../'."""
    try:
        base = os.path.realpath(PASTA_MUSICAS)
        completo = os.path.realpath(os.path.join(base, relativo))
        if os.path.commonpath([base, completo]) != base:
            return None
        return completo
    except ValueError:
        return None


def detectar_mime(dados):
    if dados.startswith(b'\x89PNG'):
        return 'image/png'
    if dados.startswith(b'\xff\xd8'):
        return 'image/jpeg'
    if dados[:3] == b'GIF':
        return 'image/gif'
    if dados[:4] == b'RIFF' and dados[8:12] == b'WEBP':
        return 'image/webp'
    return 'image/jpeg'


def extrair_capa_bytes(caminho_completo):
    try:
        audio = File(caminho_completo)
        if audio is None:
            return None
        tags = getattr(audio, 'tags', None)

        # MP3 (ID3 / APIC) — prefere a capa frontal (tipo 3)
        if tags is not None and hasattr(tags, 'getall'):
            apics = tags.getall('APIC')
            if apics:
                preferida = next((a for a in apics if a.type == 3), apics[0])
                return preferida.data

        # FLAC
        figuras = getattr(audio, 'pictures', None)
        if figuras:
            return figuras[0].data

        if tags is not None:
            # M4A / MP4
            if 'covr' in tags and tags['covr']:
                return bytes(tags['covr'][0])

            # OGG Vorbis / Opus: a imagem vem em base64 numa tag de texto
            blocos = tags.get('metadata_block_picture')
            if blocos:
                return Picture(base64.b64decode(blocos[0])).data
    except Exception:
        pass
    return None


_cache_meta = {}


def ler_metadados(caminho_completo):
    """Lê título, artista, álbum, ano e duração, com cache por data de modificação."""
    try:
        mtime = os.path.getmtime(caminho_completo)
    except OSError:
        return None

    guardado = _cache_meta.get(caminho_completo)
    if guardado and guardado[0] == mtime:
        return guardado[1]

    dados = {
        'titulo': None,
        'artista': None,
        'album': None,
        'duracao': 0,
        'ano': 0,
        'modificado': int(mtime),
    }
    try:
        meta = File(caminho_completo, easy=True)
        if meta is not None:
            chaves = {'titulo': 'title', 'artista': 'artist', 'album': 'album'}
            for campo, chave in chaves.items():
                valores = meta.get(chave)
                if valores and str(valores[0]).strip():
                    dados[campo] = str(valores[0]).strip()

            info = getattr(meta, 'info', None)
            if info is not None and getattr(info, 'length', None):
                dados['duracao'] = int(info.length)

            # Ano de lançamento: a tag 'date' pode vir como "2019" ou "2019-05-03"
            try:
                for chave in ('date', 'originaldate'):
                    valores = meta.get(chave)
                    if valores:
                        achado = re.match(r'\s*(\d{4})', str(valores[0]))
                        if achado:
                            dados['ano'] = int(achado.group(1))
                            break
            except Exception:
                pass
    except Exception:
        pass

    _cache_meta[caminho_completo] = (mtime, dados)
    return dados


# ---------- estado salvo (playlists, ordenação, volume) ----------

def estado_padrao():
    return {
        'playlists': [],
        'ordenacao': 'nome',
        'volume': 85,
        'equalizador': {'graves': 0, 'medios': 0, 'agudos': 0},
        'layout': dict(LAYOUT_PADRAO),
        'tema': dict(TEMA_PADRAO),
        'pasta_musicas': PASTA_MUSICAS,
    }


def limpar_estado(bruto):
    """Valida o que veio do navegador antes de gravar em disco."""
    estado = estado_padrao()
    if not isinstance(bruto, dict):
        return estado

    pasta_musicas = bruto.get('pasta_musicas')
    if isinstance(pasta_musicas, str):
        caminho = os.path.realpath(os.path.expanduser(pasta_musicas))
        if os.path.isdir(caminho):
            estado['pasta_musicas'] = caminho

    if bruto.get('ordenacao') in ORDENACOES:
        estado['ordenacao'] = bruto['ordenacao']

    volume = bruto.get('volume')
    if isinstance(volume, (int, float)) and not isinstance(volume, bool):
        estado['volume'] = max(0, min(100, int(volume)))

    equalizador = bruto.get('equalizador')
    if isinstance(equalizador, dict):
        for banda in estado['equalizador']:
            valor = equalizador.get(banda)
            if isinstance(valor, int) and not isinstance(valor, bool):
                estado['equalizador'][banda] = max(-12, min(12, int(round(valor))))
            elif isinstance(valor, float) and math.isfinite(valor):
                estado['equalizador'][banda] = max(-12, min(12, int(round(valor))))

    tema = bruto.get('tema')
    if isinstance(tema, dict):
        matiz = tema.get('matiz')
        if isinstance(matiz, (int, float)) and not isinstance(matiz, bool):
            estado['tema']['matiz'] = int(matiz) % 360
        if tema.get('acromatico') in ('cor', 'preto', 'branco'):
            estado['tema']['acromatico'] = tema['acromatico']
        opacidade = tema.get('opacidade')
        if isinstance(opacidade, (int, float)) and not isinstance(opacidade, bool):
            estado['tema']['opacidade'] = max(30, min(100, int(opacidade)))
        for chave in ('transparente', 'tingir', 'luz'):
            if isinstance(tema.get(chave), bool):
                estado['tema'][chave] = tema[chave]

    layout = bruto.get('layout')
    if isinstance(layout, dict):
        for chave, (minimo, maximo) in LIMITES_LAYOUT.items():
            valor = layout.get(chave)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                estado['layout'][chave] = max(minimo, min(maximo, int(valor)))

    playlists = bruto.get('playlists')
    if not isinstance(playlists, list):
        playlists = []

    ids_vistos = set()
    for p in playlists[:200]:
        if not isinstance(p, dict):
            continue
        pid = str(p.get('id') or '')[:40]
        nome = str(p.get('nome') or '').strip()[:40]
        if not pid or not nome or pid in ids_vistos:
            continue
        ids_vistos.add(pid)

        faixas, vistas = [], set()
        brutas = p.get('faixas')
        if not isinstance(brutas, list):
            brutas = []
        for f in brutas[:5000]:
            if isinstance(f, str) and f not in vistas:
                vistas.add(f)
                faixas.append(f)
        estado['playlists'].append({'id': pid, 'nome': nome, 'faixas': faixas})

    return estado


def ler_estado():
    try:
        with open(ARQUIVO_ESTADO, 'r', encoding='utf-8') as arquivo:
            return limpar_estado(json.load(arquivo))
    except (OSError, ValueError):
        return estado_padrao()


def salvar_estado(estado):
    os.makedirs(PASTA_CONFIG, exist_ok=True)
    temporario = ARQUIVO_ESTADO + '.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(estado, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_ESTADO)  # troca atômica: nunca deixa o arquivo pela metade


def caminho_recurso(relativo):
    pasta = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(pasta, relativo)


# Restaura a pasta escolhida anteriormente, se ela ainda existir.
PASTA_MUSICAS = ler_estado()['pasta_musicas']


# ---------- rotas ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/musicas')
def listar_musicas():
    lista = []
    if os.path.isdir(PASTA_MUSICAS):
        for raiz, pastas, arquivos in os.walk(PASTA_MUSICAS):
            # Ordena as pastas e ignora as ocultas
            pastas[:] = sorted((p for p in pastas if not p.startswith('.')), key=str.casefold)
            for arquivo in sorted(arquivos, key=str.casefold):
                if arquivo.startswith('.') or not arquivo.lower().endswith(EXTENSOES_VALIDAS):
                    continue
                completo = os.path.join(raiz, arquivo)
                relativo = os.path.relpath(completo, PASTA_MUSICAS).replace(os.sep, '/')
                meta = ler_metadados(completo) or {}
                lista.append({
                    'caminho': relativo,
                    'titulo': meta.get('titulo') or os.path.splitext(arquivo)[0],
                    'artista': meta.get('artista') or 'Artista desconhecido',
                    'album': meta.get('album') or '',
                    'duracao': meta.get('duracao') or 0,
                    'ano': meta.get('ano') or 0,
                    'modificado': meta.get('modificado') or 0,
                })
    return jsonify(lista)


def ler_chave_audius():
    try:
        with open(ARQUIVO_APISET, encoding='utf-8') as arquivo:
            return arquivo.read().strip()
    except FileNotFoundError:
        return ''


def salvar_chave_audius(chave):
    os.makedirs(os.path.dirname(ARQUIVO_APISET), exist_ok=True)
    descritor, temporario = tempfile.mkstemp(
        prefix='.apiset-', dir=os.path.dirname(ARQUIVO_APISET)
    )
    try:
        with os.fdopen(descritor, 'w', encoding='utf-8') as arquivo:
            arquivo.write(chave)
        if os.name == 'posix':
            os.chmod(temporario, 0o600)
        os.replace(temporario, ARQUIVO_APISET)
    except Exception:
        try:
            os.unlink(temporario)
        except FileNotFoundError:
            pass
        raise


@app.route('/api/audius/config', methods=['GET', 'PUT', 'DELETE'])
def configurar_audius():
    if request.method == 'GET':
        try:
            configurada = bool(ler_chave_audius())
        except (OSError, UnicodeError):
            app.logger.exception('Could not read Audius API key file')
            return jsonify({'erro': 'Não foi possível ler a chave do Audius.'}), 500
        return jsonify({'configurada': configurada})

    if request.method == 'PUT':
        dados = request.get_json(silent=True)
        chave = dados.get('chave') if isinstance(dados, dict) else None
        if not isinstance(chave, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', chave.strip()):
            return jsonify({'erro': 'Informe uma chave Audius válida com 40 caracteres hexadecimais.'}), 400
        try:
            salvar_chave_audius(chave.strip())
        except OSError:
            app.logger.exception('Could not save Audius API key file')
            return jsonify({'erro': 'Não foi possível salvar a chave do Audius.'}), 500
        return jsonify({'salva': True})

    try:
        os.remove(ARQUIVO_APISET)
    except FileNotFoundError:
        pass
    except OSError:
        app.logger.exception('Could not remove Audius API key file')
        return jsonify({'erro': 'Não foi possível remover a chave do Audius.'}), 500
    return jsonify({'removida': True})


class ErroApiAudius(Exception):
    pass


def consultar_api_audius(recurso, parametros, descricao):
    query = urlencode(parametros)
    cabecalhos = {'User-Agent': 'InertPlay'}
    try:
        chave_api = ler_chave_audius()
    except (OSError, UnicodeError) as erro:
        app.logger.exception('Could not read Audius API key file')
        raise ErroApiAudius('Não foi possível ler a chave do Audius.') from erro
    if re.fullmatch(r'[0-9a-fA-F]{40}', chave_api):
        cabecalhos['x-api-key'] = chave_api
    pedido = Request(
        f'https://api.audius.co/v1/{recurso}?{query}',
        headers=cabecalhos,
    )
    try:
        with urlopen(pedido, timeout=8) as resposta:
            return json.loads(resposta.read().decode('utf-8'))
    except HTTPError as erro:
        app.logger.warning('Audius %s API returned HTTP %s', recurso, erro.code)
        if erro.code in (401, 403):
            mensagem = 'A chave da API do Audius foi rejeitada. Verifique a chave nas Configurações.'
        elif erro.code == 429:
            mensagem = 'O limite de consultas do Audius foi atingido. Confira sua chave e tente novamente mais tarde.'
        else:
            mensagem = f'A API do Audius falhou na {descricao} (HTTP {erro.code}).'
        raise ErroApiAudius(mensagem) from erro
    except (URLError, TimeoutError) as erro:
        app.logger.warning('Audius %s API could not be reached', recurso)
        raise ErroApiAudius(f'Não foi possível conectar à {descricao} do Audius.') from erro
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        app.logger.warning('Audius %s API returned invalid JSON', recurso)
        raise ErroApiAudius(f'A {descricao} do Audius retornou uma resposta inválida.') from erro


@app.route('/api/audius/busca')
def buscar_musicas_audius():
    termo = request.args.get('q', '').strip()
    if len(termo) < 2 or len(termo) > 100:
        return jsonify({'erro': 'Digite uma busca entre 2 e 100 caracteres.'}), 400

    parametros = {
        'query': termo,
        'limit': 15,
        'sort_method': 'relevant',
        'app_name': 'InertPlay',
    }
    try:
        dados = consultar_api_audius('tracks/search', parametros, 'busca')
    except ErroApiAudius as erro:
        return jsonify({'erro': str(erro)}), 502

    itens = dados.get('data') if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        app.logger.warning('Audius search API returned an unexpected response shape')
        return jsonify({'erro': 'A busca do Audius retornou uma resposta inválida.'}), 502

    resultados = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        track_id = item.get('id')
        if not isinstance(track_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', track_id):
            continue
        usuario = item.get('user')
        usuario = usuario if isinstance(usuario, dict) else {}
        arte = item.get('artwork')
        arte = arte if isinstance(arte, dict) else {}
        capa = arte.get('480x480') or arte.get('150x150')
        if not isinstance(capa, str) or not capa.startswith('https://'):
            capa = None
        permalink = item.get('permalink')
        url = None
        if isinstance(permalink, str):
            caminho = urlsplit(permalink)
            if (
                not caminho.scheme
                and not caminho.netloc
                and caminho.path.startswith('/')
                and not caminho.path.startswith('//')
                and '..' not in caminho.path.split('/')
            ):
                url = 'https://audius.co' + caminho.path
        duracao = item.get('duration')
        if not isinstance(duracao, (int, float)) or isinstance(duracao, bool) or duracao < 0:
            duracao = 0
        resultados.append({
            'id': track_id,
            'titulo': str(item.get('title') or 'Sem título'),
            'artista': str(usuario.get('name') or usuario.get('handle') or 'Artista desconhecido'),
            'capa': capa,
            'duracao': duracao,
            'downloadable': item.get('is_downloadable') is True,
            'url': url,
        })
    return jsonify(resultados)


@app.route('/api/estado', methods=['GET', 'PUT'])
def estado():
    if request.method == 'GET':
        with _trava_estado:
            return jsonify(ler_estado())

    novo = limpar_estado(request.get_json(silent=True))
    try:
        with _trava_estado:
            novo['pasta_musicas'] = PASTA_MUSICAS
            salvar_estado(novo)
    except OSError:
        return jsonify({'erro': 'Não foi possível salvar'}), 500
    return jsonify(novo)


@app.route('/capa/<path:caminho_relativo>')
def obter_capa(caminho_relativo):
    completo = caminho_seguro(caminho_relativo)
    dados = None
    if completo and os.path.isfile(completo):
        dados = extrair_capa_bytes(completo)

    if dados:
        resposta = Response(dados, mimetype=detectar_mime(dados))
    else:
        resposta = Response(CAPA_PADRAO_SVG, mimetype='image/svg+xml')
    resposta.headers['Cache-Control'] = 'public, max-age=3600'
    return resposta


@app.route('/audio/<path:caminho_relativo>')
def tocar_audio(caminho_relativo):
    # send_from_directory já bloqueia '../' e suporta Range (necessário p/ avançar a faixa)
    return send_from_directory(PASTA_MUSICAS, caminho_relativo)


class ApiJanela:
    """Métodos expostos ao JavaScript por window.pywebview.api."""

    def __init__(self):
        self._janela = None

    def selecionar_pasta(self):
        global PASTA_MUSICAS

        pastas = self._janela.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=PASTA_MUSICAS,
            allow_multiple=False,
        )
        if not pastas:
            return None

        caminho = os.path.realpath(os.path.expanduser(pastas[0]))
        if not os.path.isdir(caminho):
            raise ValueError('A pasta selecionada não está disponível.')

        with _trava_estado:
            novo_estado = ler_estado()
            novo_estado['pasta_musicas'] = caminho
            salvar_estado(novo_estado)
            PASTA_MUSICAS = caminho
        return caminho

    def restaurar_janela(self, largura, altura):
        largura = max(TAMANHO_JANELA_PADRAO[0], int(largura))
        altura = max(TAMANHO_JANELA_PADRAO[1], int(altura))
        self._janela.resize(largura, altura)

    def baixar_musica_audius(self, track_id):
        if not isinstance(track_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', track_id):
            raise ValueError('Identificador de faixa inválido.')

        resposta = consultar_api_audius(
            f'tracks/{track_id}', {'app_name': 'InertPlay'}, 'verificação de download'
        )
        faixa = resposta.get('data') if isinstance(resposta, dict) else None
        if not isinstance(faixa, dict) or faixa.get('is_downloadable') is not True:
            raise ValueError('O artista não permite o download desta faixa.')

        nome = faixa.get('orig_filename') or faixa.get('title') or 'faixa-audius'
        nome = os.path.basename(str(nome).replace('\\', '/'))
        nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', nome).strip(' .')
        raiz, extensao = os.path.splitext(nome)
        if not extensao:
            extensao = '.mp3'
        nome = f'{raiz[:160] or "faixa-audius"}{extensao[:12]}'
        pasta_downloads = os.path.expanduser('~/Downloads')
        if not os.path.isdir(pasta_downloads):
            pasta_downloads = os.path.expanduser('~')

        destino = self._janela.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=pasta_downloads,
            save_filename=nome,
            file_types=('Audio files (*.mp3;*.wav;*.flac;*.m4a;*.ogg;*.opus;*.aac)',),
        )
        if not destino:
            return {'cancelado': True}
        if isinstance(destino, (list, tuple)):
            destino = destino[0] if destino else None
        if not isinstance(destino, str) or not destino:
            return {'cancelado': True}

        query = urlencode({'app_name': 'InertPlay', 'filename': nome})
        url = f'https://api.audius.co/v1/tracks/{track_id}/download?{query}'
        descritor, temporario = tempfile.mkstemp(
            prefix='.inert-download-', dir=os.path.dirname(os.path.abspath(destino))
        )
        try:
            with os.fdopen(descritor, 'wb') as arquivo:
                descritor = None
                try:
                    with urlopen(Request(url, headers={'User-Agent': 'InertPlay'}), timeout=30) as audio:
                        tipo = audio.headers.get_content_type()
                        if not tipo.startswith('audio/') and tipo not in (
                            'application/octet-stream',
                            'binary/octet-stream',
                        ):
                            raise RuntimeError('O Audius não retornou um arquivo de áudio válido.')
                        while True:
                            bloco = audio.read(64 * 1024)
                            if not bloco:
                                break
                            arquivo.write(bloco)
                except HTTPError as erro:
                    raise RuntimeError(
                        f'O Audius recusou o download (HTTP {erro.code}).'
                    ) from erro
                except (URLError, TimeoutError) as erro:
                    raise RuntimeError('Não foi possível baixar a faixa do Audius.') from erro
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, destino)
        except OSError as erro:
            raise RuntimeError('Não foi possível salvar o arquivo escolhido.') from erro
        finally:
            if descritor is not None:
                os.close(descritor)
            try:
                os.unlink(temporario)
            except FileNotFoundError:
                pass
        return {'nome': os.path.basename(destino)}


if __name__ == '__main__':
    # Servidor próprio em thread, porta livre automática: atende vários
    # pedidos ao mesmo tempo (capas + áudio) e suporta seek no áudio.
    servidor = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    api = ApiJanela()
    opcoes = dict(
        title='Inert',
        url=f'http://127.0.0.1:{servidor.server_port}/',
        width=TAMANHO_JANELA_PADRAO[0],
        height=TAMANHO_JANELA_PADRAO[1],
        min_size=(1000, 560),
        js_api=api,
    )
    if JANELA_TRANSPARENTE:
        opcoes['transparent'] = True
    else:
        opcoes['background_color'] = '#070304'
    api._janela = webview.create_window(**opcoes)
    if sys.platform.startswith('linux'):
        webview.start(gui='gtk', icon=caminho_recurso(os.path.join('static', 'icon.svg')))
    else:
        webview.start()
    servidor.shutdown()
