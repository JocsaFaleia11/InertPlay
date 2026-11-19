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

O **InertPlay** é um reprodutor de áudio para desktop Linux com design moderno, construído com Python, GTK3, WebKitGTK e GStreamer. Encontra-se atualmente em fase **Beta (v1.0.2)** e contribuições podem ser enviadas na aba [Issues](https://github.com/JocsaFaleia11/InertPlay/issues).

---

## Capturas de Tela

<img width="1440" height="900" alt="Captura_de_tela_20261119_172843" src="https://github.com/user-attachments/assets/eac0fd56-45f9-4868-9f2a-6c4ad752a37c" /> 
<img width="1440" height="900" alt="Captura_de_tela_20261119_194542" src="https://github.com/user-attachments/assets/2f6198f9-b731-41b4-b2eb-d718fce18c74" />
<img width="1440" height="900" alt="Captura_de_tela_20261119_194706" src="https://github.com/user-attachments/assets/7d91c570-add1-4cd4-a3b1-d30ed25bd07f" />
---

## Instalação

Disponível no formato `.deb` para distribuições Linux 64-bit baseadas em Debian e Ubuntu.

1. Baixe o arquivo `InertPlay_1.0.2_amd64.deb` em [Releases](https://github.com/JocsaFaleia11/InertPlay/releases/).
2. Execute no terminal:

```bash
cd ~/Downloads
sudo apt update
sudo apt install ./InertPlay_1.0.2_amd64.deb
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
