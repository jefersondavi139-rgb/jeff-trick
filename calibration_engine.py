"""
==============================================================================
  JEFF TRICK — calibration_engine.py
  Módulo de Calibragem e Precisão — Sistema de Mira
==============================================================================

  Funções implementadas:
    1. Estabilizador de Jitter   — Filtra micro-tremores do dedo/sensor
    2. Ajuste de Sensibilidade Y — Multiplicador 1.5x no eixo vertical
    3. Interpolador de Movimento — Suaviza rastro do cursor entre frames

  Uso independente:
    from calibration_engine import CalibrationEngine
    engine = CalibrationEngine()
    filtered_x, filtered_y = engine.processar(delta_x, delta_y)

  Uso via main.py:
    python main.py aim
==============================================================================
"""

import math
import time
from typing import Tuple, List, Optional
from collections import deque


# ─────────────────────────────────────────────────────────────────
# CalibrationEngine
# ─────────────────────────────────────────────────────────────────

class CalibrationEngine:
    """
    Motor de calibragem de movimento do cursor para o JEFF TRICK.

    Parâmetros ajustáveis via sensibilidade_config.json:
      jitter_threshold_ms:  Limiar de tempo (ms) abaixo do qual micro-tremores
                            são considerados jitter e filtrados.
      y_axis_multiplier:    Fator de amplificação do eixo Y para facilitar
                            a subida de capa (padrão: 1.5x).
      smooth_interpolation: Fator de suavização (0.0–1.0). Valores mais altos
                            = mais suave, porém com mais latência percebida.
      polling_rate_hz:      Taxa de sondagem do sensor de toque em Hz.
      dead_zone_pixels:     Raio em pixels onde o movimento é considerado
                            intencional (filtra tremores estáticos).
    """

    def __init__(
        self,
        jitter_threshold_ms: float = 8.0,
        y_multiplier:        float = 1.5,
        smooth_factor:       float = 0.35,
        polling_rate_hz:     int   = 240,
        dead_zone_px:        float = 2.0
    ):
        self.jitter_threshold_ms = jitter_threshold_ms
        self.y_multiplier        = y_multiplier
        self.smooth_factor       = smooth_factor
        self.polling_rate_hz     = polling_rate_hz
        self.dead_zone_px        = dead_zone_px

        # Estado interno
        self._ultimo_timestamp:    float = 0.0
        self._ultimo_x:            float = 0.0
        self._ultimo_y:            float = 0.0
        self._smooth_x:            float = 0.0
        self._smooth_y:            float = 0.0
        self._historico:           deque = deque(maxlen=8)  # Últimos 8 pontos
        self._ativo:               bool  = False

        # Estatísticas de sessão
        self._total_processado:    int   = 0
        self._total_filtrado:      int   = 0

    def inicializar(self):
        """Inicializa o motor e reseta o estado interno."""
        self._ultimo_timestamp = time.monotonic()
        self._ultimo_x         = 0.0
        self._ultimo_y         = 0.0
        self._smooth_x         = 0.0
        self._smooth_y         = 0.0
        self._historico.clear()
        self._ativo            = True
        self._total_processado = 0
        self._total_filtrado   = 0

    def exibir_config(self):
        """Exibe a configuração atual do motor no terminal."""
        print(f"""
  ┌─────────────────────────────────────────┐
  │   CalibrationEngine — JEFF TRICK        │
  ├─────────────────────────────────────────┤
  │  Jitter Threshold:  {self.jitter_threshold_ms:>6.1f} ms           │
  │  Y Multiplier:      {self.y_multiplier:>6.2f}x            │
  │  Smooth Factor:     {self.smooth_factor:>6.2f} (0.0–1.0)    │
  │  Polling Rate:      {self.polling_rate_hz:>6d} Hz           │
  │  Dead Zone:         {self.dead_zone_px:>6.1f} px           │
  └─────────────────────────────────────────┘""")

    # ──────────────────────────────────────────────────────────────
    # Pipeline principal de processamento
    # ──────────────────────────────────────────────────────────────

    def processar(self, delta_x: float, delta_y: float) -> Tuple[float, float]:
        """
        Processa um delta de movimento (dx, dy) pelo pipeline completo:
          1. Filtro de Dead Zone
          2. Estabilizador de Jitter
          3. Multiplicador de Eixo Y
          4. Interpolador de Suavização (Smooth)

        Args:
            delta_x: Deslocamento bruto no eixo X desde o último frame.
            delta_y: Deslocamento bruto no eixo Y desde o último frame.

        Returns:
            (filtered_x, filtered_y): Deltas processados prontos para aplicação.
        """
        if not self._ativo:
            return delta_x, delta_y

        self._total_processado += 1
        timestamp_atual = time.monotonic()

        # 1. Filtro de Dead Zone
        dx, dy = self._filtrar_dead_zone(delta_x, delta_y)

        # 2. Estabilizador de Jitter (baseado em tempo entre eventos)
        dx, dy = self._estabilizar_jitter(dx, dy, timestamp_atual)

        # 3. Multiplicador de Eixo Y (1.5x para subida de capa)
        dx, dy = self._aplicar_multiplicador_y(dx, dy)

        # 4. Interpolador de Movimento (Smooth)
        dx, dy = self._suavizar_movimento(dx, dy)

        # Salva estado para próxima iteração
        self._ultimo_timestamp = timestamp_atual
        self._ultimo_x         = dx
        self._ultimo_y         = dy
        self._historico.append((dx, dy, timestamp_atual))

        return dx, dy

    # ──────────────────────────────────────────────────────────────
    # Passo 1: Filtro de Dead Zone
    # ──────────────────────────────────────────────────────────────

    def _filtrar_dead_zone(self, dx: float, dy: float) -> Tuple[float, float]:
        """
        Remove movimentos menores que dead_zone_px em raio euclidiano.
        Filtra tremores estáticos sem intenção de movimento.

        Lógica:
          Se sqrt(dx² + dy²) < dead_zone_px → ignora o movimento (retorna 0,0)
          Caso contrário → subtrai o raio da zona morta do vetor de movimento
        """
        magnitude = math.sqrt(dx * dx + dy * dy)

        if magnitude < self.dead_zone_px:
            self._total_filtrado += 1
            return 0.0, 0.0

        # Normaliza e subtrai a zona morta para preservar precisão em movimentos pequenos
        fator = (magnitude - self.dead_zone_px) / magnitude
        return dx * fator, dy * fator

    # ──────────────────────────────────────────────────────────────
    # Passo 2: Estabilizador de Jitter
    # ──────────────────────────────────────────────────────────────

    def _estabilizar_jitter(
        self,
        dx: float,
        dy: float,
        timestamp: float
    ) -> Tuple[float, float]:
        """
        Filtra micro-tremores baseando-se no intervalo de tempo entre eventos.

        Lógica:
          Se o evento chega muito rápido (intervalo < jitter_threshold_ms)
          E o deslocamento muda de direção bruscamente →
          Considera como jitter e reduz a amplitude do movimento.

        A mudança de direção é detectada pelo produto escalar negativo entre
        o vetor atual e o vetor anterior (ângulo > 90°).
        """
        if self._ultimo_timestamp == 0.0:
            return dx, dy

        intervalo_ms = (timestamp - self._ultimo_timestamp) * 1000.0

        # Evento muito rápido: possível jitter
        if intervalo_ms < self.jitter_threshold_ms and intervalo_ms > 0:
            # Verifica mudança brusca de direção (produto escalar)
            produto_escalar = (dx * self._ultimo_x) + (dy * self._ultimo_y)

            if produto_escalar < 0:
                # Direção oposta em intervalo muito curto = jitter
                # Aplica fator de amortecimento proporcional à velocidade do evento
                fator_amortecimento = intervalo_ms / self.jitter_threshold_ms
                self._total_filtrado += 1
                return dx * fator_amortecimento, dy * fator_amortecimento

        return dx, dy

    # ──────────────────────────────────────────────────────────────
    # Passo 3: Multiplicador de Eixo Y
    # ──────────────────────────────────────────────────────────────

    def _aplicar_multiplicador_y(self, dx: float, dy: float) -> Tuple[float, float]:
        """
        Aplica o multiplicador de sensibilidade no eixo Y.

        Padrão: 1.5x
        Objetivo: facilitar a "subida de capa" — o movimento da mira de baixo
        para cima (eixo Y negativo no Android) que acompanha o recuo da arma.

        O eixo X permanece inalterado para preservar a precisão horizontal.
        """
        return dx, dy * self.y_multiplier

    # ──────────────────────────────────────────────────────────────
    # Passo 4: Interpolador de Movimento (Smooth)
    # ──────────────────────────────────────────────────────────────

    def _suavizar_movimento(self, dx: float, dy: float) -> Tuple[float, float]:
        """
        Suaviza o rastro do cursor entre frames usando interpolação exponencial (EMA).

        Fórmula (Exponential Moving Average):
          smooth_x = (smooth_factor × dx) + ((1 - smooth_factor) × smooth_x_anterior)

        Efeito:
          - smooth_factor = 1.0: sem suavização (resposta imediata)
          - smooth_factor = 0.0: cursor estático (suavização total)
          - smooth_factor = 0.35: equilíbrio ideal (suaviza sem latência perceptível)

        Previne que a mira "pule" o alvo por movimentos de alta frequência.
        """
        self._smooth_x = (self.smooth_factor * dx) + ((1.0 - self.smooth_factor) * self._smooth_x)
        self._smooth_y = (self.smooth_factor * dy) + ((1.0 - self.smooth_factor) * self._smooth_y)
        return self._smooth_x, self._smooth_y

    # ──────────────────────────────────────────────────────────────
    # Utilitários
    # ──────────────────────────────────────────────────────────────

    def resetar(self):
        """Reseta o estado do motor sem desativá-lo."""
        self._ultimo_x   = 0.0
        self._ultimo_y   = 0.0
        self._smooth_x   = 0.0
        self._smooth_y   = 0.0
        self._historico.clear()
        self._ultimo_timestamp = time.monotonic()

    def estatisticas(self) -> dict:
        """Retorna estatísticas da sessão atual."""
        filtrado_pct = (
            (self._total_filtrado / self._total_processado * 100)
            if self._total_processado > 0 else 0.0
        )
        return {
            "total_processado":   self._total_processado,
            "total_filtrado":     self._total_filtrado,
            "filtrado_pct":       round(filtrado_pct, 2),
            "y_multiplier":       self.y_multiplier,
            "smooth_factor":      self.smooth_factor,
            "jitter_threshold_ms": self.jitter_threshold_ms,
        }

    def __repr__(self) -> str:
        return (
            f"CalibrationEngine("
            f"jitter={self.jitter_threshold_ms}ms, "
            f"y={self.y_multiplier}x, "
            f"smooth={self.smooth_factor}, "
            f"polling={self.polling_rate_hz}Hz)"
        )
