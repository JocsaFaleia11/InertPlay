InertPlay

Um reprodutor de áudio leve e moderno para desktop Linux, desenvolvido para oferecer reprodução local rápida, organização inteligente de biblioteca e interface nativa.


Instalação no Linux (Ubuntu / Debian / KDE / Mint), 

Para instalar o **InertPlay** no seu sistema, utilize o instalador oficial `.deb` pelo terminal (o `apt` configurará automaticamente as bibliotecas gráficas e codecs de áudio necessários):

```bash
sudo apt update
sudo apt install ./InertPlay_1.0.0_amd64.deb
```

Após a instalação, o **InertPlay** estará disponível diretamente no menu de aplicativos do sistema.

---

Requisitos de Sistema

- **Sistema Operacional:** Linux 64-bit (`amd64`) baseado em Debian/Ubuntu (Ubuntu, Kubuntu, Linux Mint, Pop!_OS, KDE Neon, etc.).
- **Dependências gráficas e de mídia:** `python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-webkit2-4.1`, `gstreamer1.0-libav`, `gstreamer1.0-plugins-bad` (instaladas automaticamente via `.deb`).

---
Solução de Problemas (Em caso de não reproduzir áudio)

Se o aplicativo abrir normalmente, listar suas músicas, mas **não sair som** ao dar play (especialmente em arquivos `.m4a`, `.aac` ou `.mp3`), o seu sistema provavelmente está sem os codecs proprietários do **GStreamer** utilizados pelo motor gráfico WebKitGTK.

Para corrigir, instale o pacote completo de codecs de mídia no terminal e reinicie o aplicativo:

```bash
sudo apt update
sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly ffmpeg -y
```

* **Verifique também a pasta de músicas:** O aplicativo busca faixas na pasta padrão de músicas do sistema (`~/Músicas` ou `~/Music`). Certifique-se de que seus arquivos de áudio estão dentro desse diretório.

--

Licença e Direitos Autorais

**Copyright © 2026 InertProject. Todos os direitos reservados.**

Este software é proprietário e distribuído sob **licença fechada**.
- **Uso permitido:** Você tem permissão para instalar e utilizar o aplicativo compilado para uso pessoal ou interno.
- **Restrições:** É estritamente proibido copiar, modificar, descompilar, distribuir ou comercializar o código-fonte ou os binários deste software, no todo ou em parte, sem autorização prévia por escrito do autor.
