
**InertPlay**
<img width="1440" height="900" alt="Captura_de_tela_20261119_172812" src="https://github.com/user-attachments/assets/b3347c6c-f8b5-493c-a648-b0943f70547e" />
<img width="1440" height="900" alt="Captura_de_tela_20261119_172829" src="https://github.com/user-attachments/assets/804d2114-8ff9-4ef4-85ea-a1fd28312ee2" />


<div align="center">
  <h1>InertPlay</h1>
  <p><strong>Um player de música leve, rápido e visualmente moderno para Linux.</strong></p>
  <p>
    <a href="#sobre-o-projeto">Sobre</a> •
    <a href="#capturas-de-tela">Capturas de Tela</a> •
    <a href="#instalacao">Instalação</a> •
    <a href="#solucao-de-problemas">Solução de Problemas</a>
  </p>
</div>

---

## Sobre o Projeto

O **InertPlay** é um reprodutor de áudio para desktop Linux com design moderno, construído com Python, GTK3, WebKitGTK e GStreamer. Encontra-se atualmente em fase **Beta (v1.0.0)** e contribuições podem ser enviadas na aba [Issues](https://github.com).

---

## Capturas de Tela

| Tela Principal | Biblioteca de Músicas |
| :---: | :---: |
| ![Interface Principal](<img width="1440" height="900" alt="Captura_de_tela_20261119_172843" src="https://github.com/user-attachments/assets/eac0fd56-45f9-4868-9f2a-6c4ad752a37c" />) | ![Biblioteca](link-da-sua-imagem-2.png) |

---

## Instalação

Disponível no formato `.deb` para distribuições Linux 64-bit baseadas em Debian e Ubuntu.

1. Baixe o arquivo `InertPlay_1.0.0_amd64.deb` em [Releases](https://github.com).
2. Execute no terminal:

```bash
cd ~/Downloads
sudo apt update
sudo apt install ./InertPlay_1.0.0_amd64.deb
```

Requisitos configurados automaticamente pelo pacote: `python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-webkit2-4.1`, `gstreamer1.0-libav` e `gstreamer1.0-plugins-bad`.

---

## Solução de Problemas

* **Sem som:** Instale os codecs adicionais com:
  ```bash
  sudo apt update
  sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly ffmpeg -y
  ```
* **Músicas não aparecem:** Certifique-se de que os arquivos estão na pasta `~/Músicas` ou `~/Music`.

---

## Licença

Copyright (c) 2026 InertProject. Distribuído sob licença MIT.
