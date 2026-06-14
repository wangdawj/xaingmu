/**
 * 通用格式化工具函数
 * ==================
 * 提供数字格式化等前端展示辅助函数。
 */

/**
 * 数字格式化：>= 10000 显示万单位，否则使用千分位
 * @param {number|null} n - 原始数值
 * @returns {string} 格式化后的字符串
 */
export function fmtNum(n) {
  if (n == null || isNaN(n)) return '0'
  return n >= 10000 ? (n / 10000).toFixed(1) + '万' : n.toLocaleString('zh-CN')
}
