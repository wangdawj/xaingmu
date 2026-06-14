/**
 * 校园建筑 SVG 拓扑布局配置
 * =========================
 * 定义每个建筑在 CampusMap 组件中的位置（x, y）、图标尺寸（width, height）。
 * 坐标体系基于 800×500 的 SVG 画布。
 */

export const campusLayout = [
  { building_id: 'B001', building_name: '第一教学楼', x: 480, y: 150, width: 90, height: 60 },
  { building_id: 'B002', building_name: '第二教学楼', x: 590, y: 150, width: 90, height: 60 },
  { building_id: 'B003', building_name: '1号宿舍楼',   x: 400, y: 330, width: 90, height: 60 },
  { building_id: 'B004', building_name: '2号宿舍楼',   x: 510, y: 330, width: 90, height: 60 },
  { building_id: 'B005', building_name: '中心图书馆',  x: 350, y: 100, width: 110, height: 70 },
  { building_id: 'B006', building_name: '第一食堂',    x: 600, y: 280, width: 80, height: 60 },
  { building_id: 'B007', building_name: '体育馆',      x: 300, y: 280, width: 80, height: 60 },
  { building_id: 'B008', building_name: '行政楼',      x: 700, y: 100, width: 80, height: 60 },
]

/**
 * 根据建筑分类获取 SVG 填充色
 * @param {string} category - 建筑分类（academic/office/dormitory/canteen/library/default）
 * @returns {string} CSS rgba 颜色字符串
 */
export function getFillColor(category) {
  const colors = {
    academic: 'rgba(24,144,255,.6)',
    office: 'rgba(82,196,26,.6)',
    dormitory: 'rgba(250,140,22,.6)',
    canteen: 'rgba(245,34,45,.6)',
    library: 'rgba(114,46,209,.6)',
    default: 'rgba(144,147,153,.5)',
  }
  return colors[category] || colors.default
}
