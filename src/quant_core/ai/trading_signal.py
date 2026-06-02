"""
AI Trading Signal Service - AI驱动的交易信号生成
基于原仓库 fast_analysis 核心逻辑简化
"""
import time
import pandas as pd
from typing import Dict, Any, Optional
from quant_core.llm import get_llm_service
from quant_core.strategy.indicators import calculate_indicator


class AITradingSignal:
    """AI实时交易信号生成器"""

    def __init__(self):
        self.llm = get_llm_service()

    def generate_signal(self, df, symbol: str, current_price: float,
                        timeframe: str = "1H", language: str = "zh-CN",
                        strategy_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        AI生成实时交易信号（支持策略配置）

        Args:
            df: K线数据
            symbol: 交易对
            current_price: 当前价格
            timeframe: 时间周期
            language: 语言
            strategy_config: 策略配置，包含：
                - indicators: 要使用的指标列表 ["rsi", "macd", "boll"]
                - rsi_oversold/rsi_overbought: RSI超买超卖阈值
                - boll_position_low/boll_position_high: 布林带位置阈值
                - macd_confirm: 是否需要MACD确认
                - ma_confirmation: 是否需要均线确认
                - custom_weights: 各指标权重

        Returns:
            包含决策、置信度、止盈止损等的完整信号
        """
        start_time = time.time()

        # 多周期数据收集（用于共识）
        timeframes = self._get_consensus_timeframes(timeframe)
        all_data = {}

        for tf in timeframes:
            tf_data = self._collect_timeframe_data(df, tf, current_price)
            if tf_data:
                all_data[tf] = tf_data

        # 计算目标评分（多周期共识）
        consensus_score, objective_by_tf = self._calculate_consensus(all_data, current_price, strategy_config)

        # 构建AI分析提示
        system_prompt, user_prompt = self._build_prompt(
            all_data, current_price, symbol, language, consensus_score, objective_by_tf, strategy_config
        )

        # AI决策
        default_signal = {
            "decision": "HOLD",
            "confidence": 50,
            "action_recommendation": "等待更明确信号，暂不操作",
            "summary": "市场信号不够明确，建议等待更清晰的方向确认。建议操作：观望。",
            "entry_price": current_price,
            "stop_loss": round(current_price * 0.97, 4),
            "take_profit": round(current_price * 1.05, 4),
            "position_size_pct": 10,
            "timeframe": "medium",
            "key_reasons": ["AI分析中"],
            "risks": ["信号不确定"],
            "technical_score": 50,
            "fundamental_score": 50,
            "sentiment_score": 50,
        }

        signal = self.llm.safe_call_llm(system_prompt, user_prompt, default_signal)

        # 如果 LLM 失败（仍为默认 HOLD）但 consensus 评分有效，用评分推导信号
        try:
            is_fallback = (
                signal.get("summary") == default_signal["summary"] and
                signal.get("key_reasons") == default_signal["key_reasons"]
            )
        except Exception:
            is_fallback = False
        if is_fallback and consensus_score != 0 and all_data:
            primary_tf = next(iter(all_data.keys()), None)
            primary = all_data.get(primary_tf, {}) if primary_tf else {}
            atr = primary.get("atr") or (current_price * 0.02)
            confidence = min(85, max(50, int(50 + abs(consensus_score))))
            if consensus_score > 15:
                signal["decision"] = "BUY"
                signal["confidence"] = confidence
                signal["entry_price"] = round(current_price, 4)
                signal["stop_loss"] = round(current_price - atr * 1.5, 4)
                signal["take_profit"] = round(current_price + atr * 2.5, 4)
                signal["position_size_pct"] = min(50, max(10, int(abs(consensus_score))))
                signal["summary"] = f"多周期共识偏多（评分 +{consensus_score:.1f}），多周期技术指标同向看涨。建议操作：可在 ${signal['entry_price']} 附近分批建仓 {signal['position_size_pct']}% 仓位，止损 ${signal['stop_loss']}，止盈 ${signal['take_profit']}。"
                signal["action_recommendation"] = f"在 ${signal['entry_price']} 附近分批买入 {signal['position_size_pct']}% 仓位，止损 ${signal['stop_loss']}，止盈 ${signal['take_profit']}"
            elif consensus_score < -15:
                signal["decision"] = "SELL"
                signal["confidence"] = confidence
                signal["entry_price"] = round(current_price, 4)
                signal["stop_loss"] = round(current_price + atr * 1.5, 4)
                signal["take_profit"] = round(current_price - atr * 2.5, 4)
                signal["position_size_pct"] = min(50, max(10, int(abs(consensus_score))))
                signal["summary"] = f"多周期共识偏空（评分 {consensus_score:.1f}），多周期技术指标同向看跌。建议操作：可在 ${signal['entry_price']} 附近分批做空或减仓 {signal['position_size_pct']}%，止损 ${signal['stop_loss']}，止盈 ${signal['take_profit']}。"
                signal["action_recommendation"] = f"在 ${signal['entry_price']} 附近分批卖出 {signal['position_size_pct']}% 仓位，止损 ${signal['stop_loss']}，止盈 ${signal['take_profit']}"
            else:
                signal["decision"] = "HOLD"
                signal["confidence"] = 50
                signal["summary"] = f"多周期共识中性（评分 {consensus_score:.1f}），多空力量均衡无明确方向。建议操作：观望，等待方向突破或回踩关键支撑/阻力位后再行动。"
                signal["action_recommendation"] = "当前多空均衡，建议观望等待方向突破"
            # 用客观数据生成理由
            reasons = []
            if primary.get("rsi") is not None:
                rsi = primary["rsi"]
                if rsi < 30: reasons.append(f"RSI {rsi:.1f} 进入超卖区")
                elif rsi > 70: reasons.append(f"RSI {rsi:.1f} 进入超买区")
                else: reasons.append(f"RSI {rsi:.1f} 中性区间")
            if primary.get("macd") is not None and primary.get("macd_signal") is not None:
                if primary["macd"] > primary["macd_signal"]:
                    reasons.append("MACD 金叉状态")
                else:
                    reasons.append("MACD 死叉状态")
            if primary.get("adx") is not None and primary["adx"] > 25:
                reasons.append(f"ADX {primary['adx']:.1f} 趋势较强")
            if primary.get("change_1d") is not None:
                chg = primary["change_1d"]
                reasons.append(f"1日变化 {chg:+.2f}%")
            if not reasons:
                reasons = [f"基于 {','.join(all_data.keys())} 多周期共识评分"]
            signal["key_reasons"] = reasons
            signal["risks"] = ["未启用 LLM，信号基于规则推导，请人工复核"]
            signal["technical_score"] = max(0, min(100, int(50 + consensus_score)))

        # 兜底：如果 LLM 没返回 action_recommendation，从已有字段推导一个
        if not signal.get("action_recommendation"):
            decision = signal.get("decision", "HOLD")
            ep = signal.get("entry_price", current_price)
            sl = signal.get("stop_loss", round(current_price * 0.97, 4))
            tp = signal.get("take_profit", round(current_price * 1.05, 4))
            pct = signal.get("position_size_pct", 10)
            if decision == "BUY":
                signal["action_recommendation"] = f"在 ${ep} 附近分批买入 {pct}% 仓位，止损 ${sl}，止盈 ${tp}"
            elif decision == "SELL":
                signal["action_recommendation"] = f"在 ${ep} 附近分批卖出 {pct}% 仓位，止损 ${sl}，止盈 ${tp}"
            else:
                signal["action_recommendation"] = "当前多空均衡，建议观望等待方向突破"

        # 计算趋势展望
        trend_outlook = self._calculate_trend_outlook(objective_by_tf, consensus_score)

        # 确保信号完整
        signal["trend_outlook"] = trend_outlook
        signal["timeframe"] = timeframe
        signal["timeframes_analyzed"] = list(all_data.keys())
        signal["analysis_time_ms"] = int((time.time() - start_time) * 1000)

        # 保存到历史记忆
        try:
            from quant_core.ai.analysis_memory import get_analysis_memory
            memory = get_analysis_memory()

            # 获取主周期指标
            primary_data = all_data.get(timeframe, {}) if all_data else {}

            memory.store(
                symbol=symbol,
                decision=signal.get("decision", "HOLD"),
                confidence=signal.get("confidence", 50),
                price_at_analysis=current_price,
                summary=signal.get("summary", ""),
                reasons=signal.get("key_reasons", []),
                scores={
                    "technical": signal.get("technical_score", 50),
                    "fundamental": signal.get("fundamental_score", 50),
                    "sentiment": signal.get("sentiment_score", 50),
                },
                indicators_snapshot={
                    "rsi": primary_data.get("rsi"),
                    "macd": primary_data.get("macd"),
                    "boll_position": (current_price - primary_data.get("boll_lower", 0)) /
                                     (primary_data.get("boll_upper", 1) - primary_data.get("boll_lower", 0))
                                     if primary_data.get("boll_upper") and primary_data.get("boll_lower") else 0.5,
                },
                raw_result=signal,
                consensus_score=consensus_score,
            )
        except Exception as e:
            # 静默失败，不影响主流程
            pass

        return signal

    def _get_consensus_timeframes(self, primary_tf: str) -> list:
        """获取用于共识的时间周期"""
        tf_map = {
            "1m": ["1m", "5m", "15m"],
            "5m": ["5m", "15m", "1H"],
            "15m": ["15m", "1H", "4H"],
            "30m": ["30m", "1H", "4H"],
            "1H": ["1H", "4H", "1D"],
            "4H": ["4H", "1D"],
            "1D": ["1D"],
        }
        return tf_map.get(primary_tf, ["1H", "4H", "1D"])

    def _collect_timeframe_data(self, df, timeframe: str, current_price: float) -> Optional[Dict]:
        """收集单个时间周期的数据"""
        try:
            # 只检查数据量是否足够
            if len(df) < 10:
                return None

            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values if 'volume' in df else [0] * len(df)

            # RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if len(df) >= 14 else 50

            # MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = df['close'].ewm(span=26, adjust=False).mean().iloc[-1]
            macd = float(ema12 - ema26)

            # Signal line (9 period EMA of MACD)
            macd_ema = df['close'].ewm(span=9, adjust=False).mean().iloc[-1]
            macd_signal = float(macd_ema - ema26)  # 简化

            # 均线
            ma7 = float(df['close'].rolling(7).mean().iloc[-1]) if len(df) >= 7 else current_price
            ma25 = float(df['close'].rolling(25).mean().iloc[-1]) if len(df) >= 25 else current_price
            ma99 = float(df['close'].rolling(99).mean().iloc[-1]) if len(df) >= 99 else current_price

            # 布林带
            boll_mid = float(df['close'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else current_price
            boll_std = float(df['close'].rolling(20).std().iloc[-1]) if len(df) >= 20 else current_price * 0.02
            boll_upper = boll_mid + 2 * boll_std
            boll_lower = boll_mid - 2 * boll_std

            # ATR - 使用 pandas Series 计算
            close_shift = df['close'].shift(1)
            tr1 = df['high'] - df['low']
            tr2 = abs(df['high'] - close_shift)
            tr3 = abs(df['low'] - close_shift)
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1]) if len(df) >= 14 else boll_std

            # KDJ/Stochastic
            lowest_low = df['low'].rolling(9).min().iloc[-1]
            highest_high = df['high'].rolling(9).max().iloc[-1]
            rsv = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low) if highest_high != lowest_low else 50
            k_value = 50.0  # simplified K
            d_value = 50.0  # simplified D
            kdj_k = float(rsv * 2/3 + k_value * 1/3) if len(df) >= 9 else 50
            kdj_d = float(kdj_k * 2/3 + d_value * 1/3) if len(df) >= 9 else 50
            kdj_j = float(3 * kdj_k - 2 * kdj_d) if len(df) >= 9 else 50

            # 成交量 MA
            volume_arr = df['volume'].values if 'volume' in df else [0] * len(df)
            volume_ma = float(df['volume'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(volume_arr[-1]) if len(volume_arr) > 0 else 0
            volume_ratio = float(volume_arr[-1] / volume_ma) if volume_ma > 0 else 1

            # 波动率
            volatility = boll_std / boll_mid * 100 if boll_mid > 0 else 2

            # ADX (Average Directional Index) - 趋势强度
            close_shift = df['close'].shift(1)
            high_diff = df['high'] - df['high'].shift(1)
            low_diff = df['low'].shift(1) - df['low']
            plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
            minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

            atr_adx = atr  # 复用前面计算的 ATR
            plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr_adx) if atr_adx > 0 else 0
            minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr_adx) if atr_adx > 0 else 0
            # plus_di/minus_di 是 Series，divisor 也要是 Series
            sum_di = plus_di + minus_di
            dx = 100 * abs(plus_di - minus_di) / sum_di.replace(0, 1)
            adx = float(dx.ewm(alpha=1/14).mean().iloc[-1]) if len(df) >= 14 else 25

            # 价格变化
            change_1h = float((close[-1] - close[-4]) / close[-4] * 100) if len(close) >= 4 else 0
            change_4h = float((close[-1] - close[-16]) / close[-16] * 100) if len(close) >= 16 else 0
            change_1d = float((close[-1] - close[-24]) / close[-24] * 100) if len(close) >= 24 else 0

            return {
                "rsi": rsi,
                "macd": macd,
                "macd_signal": macd_signal,
                "ma7": ma7,
                "ma25": ma25,
                "ma99": ma99,
                "boll_upper": boll_upper,
                "boll_mid": boll_mid,
                "boll_lower": boll_lower,
                "atr": atr,
                "volatility": volatility,
                "adx": adx,
                "change_1h": change_1h,
                "change_4h": change_4h,
                "change_1d": change_1d,
                "volume": float(volume[-1]) if len(volume) > 0 else 0,
                "volume_ma": volume_ma,
                "volume_ratio": volume_ratio,
                "kdj_k": kdj_k,
                "kdj_d": kdj_d,
                "kdj_j": kdj_j,
                "current_price": current_price,
            }
        except Exception as e:
            return None

    def _calculate_consensus(self, all_data: Dict[str, Dict], current_price: float, strategy_config: Dict = None) -> tuple:
        """计算多周期共识评分（支持策略配置）"""
        if not all_data:
            return 0, {}

        scores = []
        objective_by_tf = {}

        for tf, data in all_data.items():
            score = self._objective_score(data, current_price, strategy_config)
            scores.append(score)
            objective_by_tf[tf] = {
                "overall_score": score,
                "decision": self._score_to_decision(score),
            }

        consensus = sum(scores) / len(scores) if scores else 0
        return consensus, objective_by_tf

    def _objective_score(self, data: Dict, current_price: float, strategy_config: Dict = None) -> float:
        """计算单个周期的客观评分（支持策略配置 + 自适应权重 + 市场状态感知）"""
        score = 0
        weight = 0

        # 从策略配置获取参数，默认值
        indicators = strategy_config.get("indicators", ["rsi", "macd", "boll"]) if strategy_config else ["rsi", "macd", "boll"]
        base_rsi_oversold = strategy_config.get("rsi_oversold", 30) if strategy_config else 30
        base_rsi_overbought = strategy_config.get("rsi_overbought", 70) if strategy_config else 70
        boll_pos_low = strategy_config.get("boll_position_low", 0.2) if strategy_config else 0.2
        boll_pos_high = strategy_config.get("boll_position_high", 0.8) if strategy_config else 0.8
        use_macd_confirm = strategy_config.get("macd_confirm", True) if strategy_config else True
        use_ma_confirm = strategy_config.get("ma_confirmation", True) if strategy_config else True
        use_kdj_confirm = strategy_config.get("kdj_confirm", False) if strategy_config else False
        use_volume_confirm = strategy_config.get("volume_confirm", False) if strategy_config else False
        volume_ratio_threshold = strategy_config.get("volume_ratio_threshold", 1.5) if strategy_config else 1.5

        # === 市场状态感知 ===
        # 1. 计算 ADX (趋势强度)
        adx = data.get("adx", 25)  # 默认 25 表示无明显趋势
        is_strong_trend = adx > 25
        is_very_strong_trend = adx > 40

        # 2. 波动率自适应 RSI 阈值
        volatility = data.get("volatility", 2)
        # 波动率调整：波动率越高，阈值越宽
        vol_adjustment = min(max((volatility - 2) * 2, 0), 15)  # 调整范围 0-15
        rsi_oversold = max(base_rsi_oversold - vol_adjustment, 20)  # 最低 20
        rsi_overbought = min(base_rsi_overbought + vol_adjustment, 80)  # 最高 80

        # 3. 根据趋势强度调整权重
        if is_very_strong_trend:
            # 强趋势市场：信任趋势指标（MACD、均线），降低震荡指标权重（RSI、K DJ）
            rsi_weight = 10  # 从 25 降到 10
            macd_weight = 30  # 从 20 升到 30
            ma_weight = 25   # 从 15 升到 25
            kdj_weight = 3   # 从 10 降到 3
            boll_weight = 7  # 从 15 降到 7
        elif is_strong_trend:
            # 中等趋势：略微提升趋势指标
            rsi_weight = 20
            macd_weight = 25
            ma_weight = 20
            kdj_weight = 8
            boll_weight = 12
        else:
            # 震荡市场：信任震荡指标，降低趋势指标
            rsi_weight = 30
            macd_weight = 15
            ma_weight = 10
            kdj_weight = 15
            boll_weight = 20

        # === RSI 评分 ===
        if "rsi" in indicators:
            rsi = data.get("rsi", 50)
            if rsi < rsi_oversold:
                # 超卖区域 - 距离越远分数越高
                oversold_depth = (rsi_oversold - rsi) / rsi_oversold
                score += 20 * (1 + oversold_depth * 2)
            elif rsi > rsi_overbought:
                # 超买区域 - 距离越远分数越低（负向）
                overbought_depth = (rsi - rsi_overbought) / (100 - rsi_overbought)
                score -= 20 * (1 + overbought_depth * 2)
            else:
                # 中性区域 - 使用 sigmoid 曲线平滑评分
                mid_rsi = (rsi_oversold + rsi_overbought) / 2
                normalized = (rsi - mid_rsi) / (rsi_overbought - rsi_oversold)
                score += (1 / (1 + 2.718 ** (-normalized * 5)) - 0.5) * 10
            weight += rsi_weight

        # === MACD 评分 ===
        if "macd" in indicators:
            macd = data.get("macd", 0)
            macd_signal = data.get("macd_signal", 0)
            # 考虑 MACD 强度（零轴上方/下方 + 背离）
            macd_histogram = macd - macd_signal
            macd_on_zero = 1 if (macd > 0 and macd_signal > 0) else 0.5 if macd > 0 else 0

            if use_macd_confirm:
                if macd_histogram > 0:
                    score += 15 * (1 + macd_on_zero * 0.5)
                else:
                    score -= 15 * (1 + (1 - macd_on_zero) * 0.5)
                weight += macd_weight
            else:
                if macd_histogram > 0:
                    score += 8 * (1 + macd_on_zero * 0.5)
                else:
                    score -= 8
                weight += macd_weight * 0.6

        # === 均线趋势评分 ===
        if "ma" in indicators and use_ma_confirm:
            ma7 = data.get("ma7", current_price)
            ma25 = data.get("ma25", current_price)
            ma99 = data.get("ma99", current_price)
            ma_score = 0
            # 多头排列
            if ma7 > ma25 > ma99:
                ma_score = 12
            elif ma7 < ma25 < ma99:
                ma_score = -12
            elif ma7 > ma25:  # 部分多头
                ma_score = 4
            elif ma7 < ma25:  # 部分空头
                ma_score = -4

            # 趋势市场中，均线信号更强
            if is_strong_trend:
                ma_score *= 1.3
            score += ma_score
            weight += ma_weight

        # === 布林带位置评分 ===
        if "boll" in indicators:
            boll_upper = data.get("boll_upper", current_price * 1.05)
            boll_lower = data.get("boll_lower", current_price * 0.95)
            boll_mid = data.get("boll_mid", current_price)
            boll_pos = (current_price - boll_lower) / (boll_upper - boll_lower) if boll_upper != boll_lower else 0.5

            # 布林带带宽（波动率指标）
            bandwidth = (boll_upper - boll_lower) / boll_mid
            is_wide_boll = bandwidth > 0.1  # 宽波段

            if boll_pos < boll_pos_low:
                # 接近下轨
                depth = (boll_pos_low - boll_pos) / boll_pos_low
                boll_score = 10 * (1 + depth)
                # 震荡市场中布林带更可靠
                if not is_strong_trend:
                    boll_score *= 1.2
                score += boll_score
            elif boll_pos > boll_pos_high:
                # 接近上轨
                depth = (boll_pos - boll_pos_high) / (1 - boll_pos_high)
                boll_score = 10 * (1 + depth)
                if not is_strong_trend:
                    boll_score *= 1.2
                score -= boll_score
            weight += boll_weight

        # === KDJ 评分 ===
        if "kdj" in indicators or use_kdj_confirm:
            kdj_k = data.get("kdj_k", 50)
            kdj_d = data.get("kdj_d", 50)
            kdj_j = data.get("kdj_j", 50)
            kdj_score = 0

            # 金叉/死叉
            if kdj_k > kdj_d and kdj_j < 30:
                kdj_score = 8  # 低位金叉，看涨
            elif kdj_k < kdj_d and kdj_j > 70:
                kdj_score = -8  # 高位死叉，看跌
            elif kdj_k > kdj_d:
                kdj_score = 3   # 普通金叉
            elif kdj_k < kdj_d:
                kdj_score = -3  # 普通死叉

            # 强趋势市场中 KDJ 容易失效，降低权重
            if is_very_strong_trend:
                kdj_score *= 0.3
            elif is_strong_trend:
                kdj_score *= 0.6

            score += kdj_score
            weight += kdj_weight

        # === 成交量评分 ===
        if "volume" in indicators or use_volume_confirm:
            volume_ratio = data.get("volume_ratio", 1)
            vol_score = 0
            if volume_ratio >= volume_ratio_threshold:
                # 放量配合方向
                if score > 0:
                    vol_score = 5  # 放量上涨
                elif score < 0:
                    vol_score = -5  # 放量下跌
                else:
                    vol_score = 2  # 中性放量
            elif volume_ratio < 0.5:
                vol_score = -2  # 缩量，可能盘整
            score += vol_score
            weight += 10

        # === 波动率评分 ===
        if "volatility" in indicators:
            volatility = data.get("volatility", 2)
            if volatility > 5:
                score -= 3  # 高波动，降低评分
            elif volatility < 1:
                score -= 1  # 低波动也有风险（可能盘整突破前）
            weight += 5

        return (score / weight * 100) if weight > 0 else 0

    def _score_to_decision(self, score: float) -> str:
        """评分转决策"""
        if score >= 20:
            return "BUY"
        elif score <= -20:
            return "SELL"
        return "HOLD"

    def _build_prompt(self, all_data: Dict[str, Dict], current_price: float,
                      symbol: str, language: str, consensus_score: float,
                      objective_by_tf: Dict, strategy_config: Dict = None) -> tuple:
        """构建AI分析提示（支持策略配置）"""

        is_zh = language.lower().startswith("zh")

        # 构建策略配置说明
        strategy_note = ""
        if strategy_config:
            indicators = strategy_config.get("indicators", ["rsi", "macd", "boll"])
            strategy_note = f"""
用户策略配置:
- 使用指标: {', '.join(indicators)}
- RSI超卖区间: <{strategy_config.get('rsi_oversold', 30)}, 超买区间: >{strategy_config.get('rsi_overbought', 70)}
- 布林带低位: <{strategy_config.get('boll_position_low', 0.2)*100:.0f}%, 高位: >{strategy_config.get('boll_position_high', 0.8)*100:.0f}%
- MACD确认: {'是' if strategy_config.get('macd_confirm', True) else '否'}
- 均线确认: {'是' if strategy_config.get('ma_confirmation', True) else '否'}

请根据以上策略配置，结合技术指标给出交易建议。"""

        system_prompt = f"""你是一个专业的加密货币交易分析师。基于多周期技术分析数据和用户策略配置，给出明确、可执行、不模棱两可的交易建议。

输出格式(JSON):
{{
    "decision": "BUY|SELL|HOLD",
    "confidence": 0-100,
    "action_recommendation": "一句话明确的可执行操作指令",
    "summary": "简要分析总结",
    "entry_price": 建议入场价,
    "stop_loss": 止损价,
    "take_profit": 止盈价,
    "position_size_pct": 建议仓位比例(1-100),
    "timeframe": "short|medium|long",
    "key_reasons": ["原因1", "原因2", "原因3"],
    "risks": ["风险1", "风险2"],
    "technical_score": 0-100,
    "fundamental_score": 0-100,
    "sentiment_score": 0-100
}}

注意:
- decision: BUY=买入, SELL=卖出, HOLD=观望
- confidence: 越高表示信号越确定。**禁用"为了安全起见给个低分"这种保守倾向** —— 应当基于多周期共识评分与技术指标的实际强度给出真实判断:
    * 共识评分绝对值 >= 30 且多周期同向 → confidence 应在 70-90
    * 共识评分绝对值 15-30 且有 2 个周期同向 → confidence 应在 60-75
    * 共识评分绝对值 < 15 或多周期矛盾 → confidence 50-60 (观望)
    * 单边强信号(ADX>40 + MACD 同向 + 价格突破) → confidence 可达 85-95
- action_recommendation: 必须是**具体可执行**的一句话操作指令，不要泛泛而谈。示例:
    * "立即在 $0.865 附近买入 30% 仓位，止损 $0.840，止盈 $0.920"
    * "等待回调至 $0.840-0.850 区间后买入，止损下破 $0.820 离场"
    * "当前处于震荡区间，建议观望不操作，等待方向突破"
    * "立即卖出 50% 仓位，止损 $0.890，止盈 $0.820"
    * "反弹至 $0.880 阻力位附近做空，止损 $0.895，止盈 $0.840"
- 入场/止损/止盈价格必须是具体数字
- key_reasons: 给出3个最关键的理由（基于具体技术指标读数）
- summary: 100字以内的简明总结，必须在最后明确写出"建议操作：XXXXX"
- 必须严格遵循用户策略配置的指标阈值"""

        # 主周期数据
        primary_data = list(all_data.values())[0]

        # 构建用户提示
        trend_map = {
            "BUY": "看涨" if is_zh else "bullish",
            "SELL": "看跌" if is_zh else "bearish",
            "HOLD": "震荡" if is_zh else "neutral"
        }

        # 周期分析摘要
        tf_analysis = []
        for tf, data in all_data.items():
            rsi = data.get("rsi", 50)
            macd = data.get("macd", 0)
            macd_signal = data.get("macd_signal", 0)
            tf_trend = "多头" if macd > macd_signal else "空头"
            rsi_status = "超卖" if rsi < 30 else "超买" if rsi > 70 else "中性"
            tf_analysis.append(f"{tf}: RSI={rsi:.1f}, MACD={tf_trend}, 状态={rsi_status}")

        user_prompt = f"""交易对: {symbol}
当前价格: ${current_price:.4f}
共识评分: {consensus_score:.2f} ({trend_map.get(self._score_to_decision(consensus_score), 'HOLD')})
{strategy_note if strategy_note else ''}
多周期分析:
{chr(10).join(tf_analysis)}

主周期技术指标:
- RSI(14): {primary_data.get('rsi', 0):.2f}
- MACD: {primary_data.get('macd', 0):.4f}
- 布林上轨: ${primary_data.get('boll_upper', 0):.4f}
- 布林中轨: ${primary_data.get('boll_mid', 0):.4f}
- 布林下轨: ${primary_data.get('boll_lower', 0):.4f}
- ATR: {primary_data.get('atr', 0):.4f}
- ADX: {primary_data.get('adx', 0):.1f}
- KDJ(K/D/J): {primary_data.get('kdj_k', 0):.1f} / {primary_data.get('kdj_d', 0):.1f} / {primary_data.get('kdj_j', 0):.1f}
- 波动率: {primary_data.get('volatility', 0):.2f}%
- 1h涨跌: {primary_data.get('change_1h', 0):.2f}%
- 4h涨跌: {primary_data.get('change_4h', 0):.2f}%
- 日涨跌: {primary_data.get('change_1d', 0):.2f}%
- 量比(vol/current_avg): {primary_data.get('volume_ratio', 0):.2f}

要求:
1. 给出明确的 decision (BUY/SELL/HOLD)，不要回避方向
2. confidence 必须与信号强度匹配（参考系统提示中的评分标准）
3. action_recommendation 必须是可直接执行的操作指令（含价格、仓位比例或触发条件）
4. summary 最后必须明确"建议操作：XXXXX"

请严格基于上述指标数据给出交易建议:"""

        return system_prompt, user_prompt

    def _calculate_trend_outlook(self, objective_by_tf: Dict, consensus_score: float) -> Dict:
        """计算趋势展望"""
        def trend_strength(score_val: float) -> str:
            a = abs(float(score_val))
            if a >= 70:
                return "strong"
            if a >= 40:
                return "moderate"
            if a >= 20:
                return "mild"
            return "neutral"

        # 从各周期提取评分
        score_1d = float((objective_by_tf.get("1D") or {}).get("overall_score", consensus_score) or consensus_score)
        score_4h = float((objective_by_tf.get("4H") or {}).get("overall_score", score_1d) or score_1d)
        score_1h = float((objective_by_tf.get("1H") or {}).get("overall_score", score_4h) or score_4h)

        # 计算各时间范围评分
        score_24h = score_1h
        score_3d = score_1d * 0.7 + score_4h * 0.3
        score_1w = score_1d

        def _decision(score):
            d = self._score_to_decision(score)
            return {"BUY": "看涨", "SELL": "看跌", "HOLD": "震荡"}.get(d, "震荡")

        return {
            "next_24h": {
                "score": round(score_24h, 2),
                "trend": _decision(score_24h),
                "strength": trend_strength(score_24h),
            },
            "next_3d": {
                "score": round(score_3d, 2),
                "trend": _decision(score_3d),
                "strength": trend_strength(score_3d),
            },
            "next_1w": {
                "score": round(score_1w, 2),
                "trend": _decision(score_1w),
                "strength": trend_strength(score_1w),
            },
        }


def get_ai_signal_service() -> AITradingSignal:
    """获取AI信号服务实例"""
    return AITradingSignal()
