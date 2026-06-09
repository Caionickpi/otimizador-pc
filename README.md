# Otimizador PC

Programa de terminal (TUI) em **português do Brasil** para **diagnóstico e
ajustes seguros** de computadores **Windows 10 e 11**.

O foco número 1 é **segurança**: o programa nunca aplica nada sem **descrever**
o que fará, **criar backup / ponto de restauração**, **pedir confirmação** e
**registrar tudo em log**. Toda alteração é **reversível**.

> Fluxo do programa: **diagnosticar → analisar/recomendar → aplicar os ajustes
> escolhidos** (sempre com backup antes).

---

## ✨ Recursos

- **Diagnóstico completo** (somente leitura): sistema, CPU, RAM (com velocidade
  dos módulos), discos (detecta **SSD x HDD** e saúde), GPU, placa-mãe/BIOS,
  rede (IP/DNS), inicialização, plano de energia e **notebook x desktop**.
- **Recomendações personalizadas** com base no hardware real (ex.: nunca sugere
  desfragmentar SSD — sugere TRIM).
- **Categorias de ajuste**, cada uma com backup + confirmação + log:
  1. Limpeza de arquivos temporários
  2. Gerenciamento de inicialização (reversível)
  3. Otimização de serviços (apenas uma *whitelist* curada)
  4. Plano de energia (adaptado a desktop/notebook)
  5. Otimização de rede (flush DNS, renovar IP, Winsock, DNS rápido)
  6. Efeitos visuais / desempenho
  7. Otimização de disco (desfragmenta só HDD; TRIM em SSD)
- **Mecanismos de segurança**: ponto de restauração do sistema, backup de
  registro (`.reg`), **modo simulação (dry-run)**, confirmação dupla, **desfazer
  última alteração** e logging completo.

---

## 🛡️ O que o programa **nunca** faz

- Nunca desativa antivírus, Windows Defender ou firewall.
- Nunca apaga arquivos pessoais (documentos, fotos, downloads, área de
  trabalho). Só mexe em **cache/temporários conhecidos**.
- Nunca toca em serviços/chaves críticos que impeçam o Windows de iniciar.
- Nunca faz alteração irreversível sem confirmação explícita e backup prévio.

---

## 📋 Requisitos

- **Windows 10 ou 11** (x64).
- **Python 3.11+** — necessário apenas para rodar a partir do código-fonte ou
  para gerar o `.exe`. O executável final **não** exige Python instalado.

---

## 🚀 Instalação (a partir do código-fonte)

1. Abra o **Prompt de Comando** ou **PowerShell** na pasta do projeto.
2. (Recomendado) crie um ambiente virtual:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale as dependências:

   ```bat
   pip install -r requirements.txt
   ```

---

## ▶️ Como rodar

```bat
python main.py
```

- O **diagnóstico** e as **recomendações** funcionam **sem** privilégios de
  administrador.
- Para **aplicar ajustes**, o programa detecta se você é administrador e, se
  não for, **oferece reabrir elevado** (vai aparecer o aviso do Windows/UAC).
- Para já começar com tudo liberado, você também pode abrir o
  **Prompt de Comando como administrador** e rodar `python main.py`.

> 💡 **Dica:** ative o **Modo simulação** (opção 10 do menu) para ver exatamente
> o que cada ajuste faria, sem alterar nada.

---

## 📦 Gerar o executável (`.exe`) com PyInstaller

Com as dependências instaladas (o `pyinstaller` já vem no `requirements.txt`),
rode na **raiz do projeto**, no Windows:

```bat
pyinstaller --onefile --console --name OtimizadorPC --add-data "dados\servicos_seguros.json;dados" --hidden-import win32timezone --hidden-import wmi main.py
```

Detalhes:

- `--onefile` gera um único `OtimizadorPC.exe` (em `dist\`).
- `--add-data "dados\servicos_seguros.json;dados"` embute a lista de serviços
  (no Windows o separador é `;`).
- `--hidden-import win32timezone --hidden-import wmi` garantem que os módulos do
  WMI/pywin32 entrem no pacote.
- As pastas `logs\` e `backups\` são criadas automaticamente **ao lado do
  `.exe`** na primeira execução.

### (Opcional) já abrir pedindo administrador

Se quiser que o `.exe` **sempre** abra solicitando elevação, adicione
`--uac-admin`:

```bat
pyinstaller --onefile --console --name OtimizadorPC --uac-admin --add-data "dados\servicos_seguros.json;dados" --hidden-import win32timezone --hidden-import wmi main.py
```

> Observação: com `--uac-admin`, mesmo o diagnóstico (que não precisa de admin)
> abrirá o UAC. Sem essa opção, o próprio programa oferece a elevação quando
> necessário — comportamento recomendado.

---

## 🗂️ Estrutura do projeto

```
otimizador-pc/
├── main.py                     # Ponto de entrada e menu principal
├── config.py                   # Constantes e estado global
├── requirements.txt
├── README.md
├── modulos/
│   ├── diagnostico.py          # Detecção de hardware/software (leitura)
│   ├── recomendacoes.py        # Análise do perfil + sugestões
│   ├── seguranca.py            # Restauração, backups, logging, desfazer
│   ├── interface.py            # Componentes da TUI (rich + questionary)
│   ├── elevacao.py             # Privilégios de administrador
│   └── tweaks/
│       ├── limpeza.py
│       ├── inicializacao.py
│       ├── servicos.py
│       ├── energia.py
│       ├── rede.py
│       ├── visual.py
│       └── disco.py
├── dados/
│   └── servicos_seguros.json   # Whitelist de serviços seguros
├── logs/                       # Logs (gerados em tempo de execução)
└── backups/                    # Backups de registro (.reg) e histórico
```

---

## ↩️ Como desfazer alterações

- **Desfazer última alteração** (opção 11 do menu) reverte a última mudança
  registrada (serviço, DNS, plano de energia, inicialização ou efeitos visuais).
- Os **backups de registro** ficam em `backups\*.reg`. Você pode aplicá-los
  manualmente dando duplo clique ou com `reg import "arquivo.reg"`.
- Em último caso, use a **Restauração do Sistema** do Windows (o programa cria
  um ponto antes de cada sessão de alterações).

---

## 🧾 Logs

Cada execução grava em `logs\otimizador_AAAA-MM-DD.log`, com data, hora, ação e
resultado (sucesso/erro). Veja-os pelo menu (opção 12) ou abrindo o arquivo.

---

## ⚠️ Aviso

Esta ferramenta foi feita para ser conservadora e segura, mas mexer em um
sistema operacional sempre envolve algum risco. Use com responsabilidade,
mantenha backups dos seus dados importantes e prefira o **Modo simulação** se
estiver em dúvida.
