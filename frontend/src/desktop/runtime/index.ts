/**
 * Desktop runtime (DLR). External import path stays English.
 * Implementation modules use Chinese identifiers per project convention.
 */
export {
  资源缓存,
  创建对象地址缓存,
} from './resource-cache'

export {
  探测低内存,
  是否低内存生效,
  低内存生效,
  低内存策略,
  应用低内存样式到根,
  低内存状态,
  type 低内存模式,
  type 低内存探测结果,
} from './low-memory'

export {
  同步缓存配额,
  标记应用活跃,
  标记应用空闲,
  注册应用释放回调,
  登记预览对象地址,
  读取预览对象地址,
  释放预览对象地址,
  写入通用缓存,
  读取通用缓存,
  清空全部可释放缓存,
  窗内容空闲毫秒,
  是否应冷启动内容,
  桌面资源管理器,
} from './desktop-resource-manager'
