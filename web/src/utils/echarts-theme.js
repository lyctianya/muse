/* ECharts 全局主题：与 theme.css 配色对齐 */
import * as echarts from 'echarts'

const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'

echarts.registerTheme('stockpulse', {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: FONT, color: '#4e5969' },
  color: ['#2f6bff', '#e5484d', '#18a058', '#d3a24a', '#7c6ff0', '#14c9c9', '#f78a1c', '#86909c'],
  categoryAxis: {
    axisLine: { lineStyle: { color: '#dfe2ea' } },
    axisTick: { show: false },
    axisLabel: { color: '#86909c', fontSize: 11 },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#86909c', fontSize: 11 },
    splitLine: { lineStyle: { color: '#eef0f4', type: 'dashed' } },
  },
  tooltip: {
    backgroundColor: 'rgba(26,35,64,0.92)',
    borderWidth: 0,
    textStyle: { color: '#fff', fontSize: 12 },
    axisPointer: { lineStyle: { color: '#c9cdd4' } },
  },
  candlestick: {
    itemStyle: {
      color: '#e5484d', color0: '#18a058',
      borderColor: '#e5484d', borderColor0: '#18a058',
    },
  },
})

/** 带统一主题的 echarts.init */
export function initChart(el, opts) {
  return echarts.init(el, 'stockpulse', opts)
}

export { echarts }
