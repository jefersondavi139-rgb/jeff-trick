"""
==============================================================================
  JEFF TRICK — main.py
  Código Principal e Inicialização do Sistema de Calibragem
==============================================================================

  Uso:
    python main.py [modo]

  Modos disponíveis:
    celular      Otimiza Touch Sampling Rate e DPI para Redmi/Android
    mobilador    Filtra Polling Rate de Mouse USB/Bluetooth
    aim          Ativa estabilização de mira e precisão de eixo Y

  Requisito:
    Execute em ambiente com ADB conectado ao dispositivo:
    adb shell pm grant com.jefftrick.app android.permission.WRITE_SECURE_SETTINGS

  Descrição:
    Este script é o ponto de entrada do sistema de calibragem do JEFF TRICK.
    Ele orquestra o calibration_engine.py, carrega os presets do arquivo
    sensibilidade_config.json e aplica as configurações via comandos ADB.
==============================================================================
"""

import sys
import json
import subprocess
import os
from calibration_engine import CalibrationEngine


# ─────────────────────────────────────────────────────────────────
# Configurações globais
# ─────────────────────────────────────────────────────────────────

CONFIG_FILE  = os.path.join(os.path.dirname(__file__), "sensibilidade_config.json")
ADB_COMMAND  = "adb"

# Cores ANSI para terminal
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
RESET   = "\033[0m"
BOLD    = "\033[1m"


# ─────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
{CYAN}{BOLD}
  ╔══════════════════════════════════════════╗
  ║          J E F F   T R I C K            ║
  ║    Performance Extrema — Free Fire       ║
  ╚══════════════════════════════════════════╝
{RESET}""")


# ─────────────────────────────────────────────────────────────────
# Carregamento de configuração
# ─────────────────────────────────────────────────────────────────

def carregar_config() -> dict:
    """Carrega o arquivo sensibilidade_config.json com os presets de calibragem."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"{GREEN}✓ Configuração carregada: {CONFIG_FILE}{RESET}")
        return config
    except FileNotFoundError:
        print(f"{RED}✗ Arquivo não encontrado: {CONFIG_FILE}{RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{RED}✗ Erro no JSON: {e}{RESET}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Execução de comandos ADB
# ─────────────────────────────────────────────────────────────────

def executar_adb(comando: str) -> bool:
    """
    Executa um comando via ADB shell no dispositivo conectado.

    Args:
        comando: Comando shell a executar no dispositivo Android.

    Returns:
        True se o comando foi executado com sucesso (exit code 0).
    """
    cmd_completo = f"{ADB_COMMAND} shell {comando}"
    print(f"  {YELLOW}→{RESET} {cmd_completo}")

    try:
        result = subprocess.run(
            cmd_completo,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True
        else:
            print(f"  {RED}Erro: {result.stderr.strip()}{RESET}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  {RED}Timeout ao executar: {cmd_completo}{RESET}")
        return False
    except Exception as e:
        print(f"  {RED}Exceção: {e}{RESET}")
        return False


def aplicar_modo(nome_modo: str, config: dict) -> bool:
    """
    Aplica um conjunto de comandos shell para o modo especificado.

    Args:
        nome_modo: 'celular', 'mobilador' ou 'aim'
        config:    Configuração carregada do JSON

    Returns:
        True se todos os comandos foram aplicados com sucesso.
    """
    modo_key = f"modo_{nome_modo}"

    if modo_key not in config:
        print(f"{RED}✗ Modo desconhecido: {nome_modo}{RESET}")
        print(f"  Modos disponíveis: celular, mobilador, aim")
        return False

    modo = config[modo_key]
    nome_display = modo.get("nome", nome_modo.upper())
    descricao    = modo.get("descricao", "")
    comandos     = modo.get("comandos_shell", [])
    avisos       = modo.get("avisos", [])

    print(f"\n{CYAN}{BOLD}[ {nome_display} ]{RESET}")
    print(f"  {descricao}\n")

    sucesso = 0
    falhas  = 0

    for cmd in comandos:
        if executar_adb(cmd):
            sucesso += 1
        else:
            falhas += 1

    # Exibe avisos manuais
    if avisos:
        print(f"\n{YELLOW}⚠  Ajustes manuais necessários:{RESET}")
        for aviso in avisos:
            print(f"   • {aviso}")

    print(f"\n  Resultado: {GREEN}{sucesso} OK{RESET} / {RED}{falhas} falhas{RESET}")
    return falhas == 0


# ─────────────────────────────────────────────────────────────────
# Inicialização com CalibrationEngine
# ─────────────────────────────────────────────────────────────────

def inicializar_calibragem(config: dict, modo: str):
    """
    Inicializa o motor de calibragem com as configurações do modo selecionado.
    Aplica filtros de jitter, multiplicador Y e suavização de movimento.
    """
    modo_key = f"modo_{modo}"
    params   = config.get(modo_key, {}).get("calibragem", {})

    if not params:
        print(f"{YELLOW}⚠ Sem parâmetros de calibragem para o modo: {modo}{RESET}")
        return

    print(f"\n{CYAN}Inicializando motor de calibragem...{RESET}")

    engine = CalibrationEngine(
        jitter_threshold  = params.get("jitter_threshold_ms",   8),
        y_multiplier      = params.get("y_axis_multiplier",     1.5),
        smooth_factor     = params.get("smooth_interpolation",  0.35),
        polling_rate_hz   = params.get("polling_rate_hz",       240),
        dead_zone_px      = params.get("dead_zone_pixels",      2)
    )

    engine.inicializar()
    engine.exibir_config()


# ─────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────

def main():
    print_banner()
    config = carregar_config()

    # Lê modo da linha de comando ou exibe menu interativo
    if len(sys.argv) > 1:
        modo = sys.argv[1].lower()
    else:
        print(f"  Selecione o modo:\n")
        print(f"  {CYAN}1{RESET} — MODO CELULAR    (Touch Sampling + DPI)")
        print(f"  {YELLOW}2{RESET} — MODO MOBILADOR  (Polling Rate 1:1)")
        print(f"  {GREEN}3{RESET} — MODO AIM         (Estabilização de Mira)")
        print()

        opcao = input("  → Opção: ").strip()
        modos_map = {"1": "celular", "2": "mobilador", "3": "aim"}
        modo = modos_map.get(opcao, "")

        if not modo:
            print(f"{RED}✗ Opção inválida.{RESET}")
            sys.exit(1)

    # Aplica o modo selecionado
    print(f"\n{BOLD}Aplicando {modo.upper()}...{RESET}\n")
    ok = aplicar_modo(modo, config)

    # Inicializa o motor de calibragem para o modo
    inicializar_calibragem(config, modo)

    if ok:
        print(f"\n{GREEN}{BOLD}✓ JEFF TRICK [{modo.upper()}] ATIVO{RESET}\n")
    else:
        print(f"\n{RED}✗ Erros durante a aplicação. Verifique a conexão ADB.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
