export interface WallpaperProcessOptions {
  maxSize?: number
  ratio?: number
  quality?: number
}

export interface ProcessedWallpaper {
  dataUrl: string
  width: number
  height: number
}

const DEFAULT_MAX_SIZE = 1920
const DEFAULT_QUALITY = 0.9

function readImageFile(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('WALLPAPER_IMAGE_LOAD_FAILED'))
    }
    image.src = url
  })
}

function readTargetRatio(ratio?: number): number {
  if (typeof ratio === 'number' && Number.isFinite(ratio) && ratio > 0) return ratio
  const width = Math.max(1, window.innerWidth || screen.width || 16)
  const height = Math.max(1, window.innerHeight || screen.height || 9)
  return width / height
}

export async function processWallpaperFile(file: File, options: WallpaperProcessOptions = {}): Promise<ProcessedWallpaper> {
  if (!file.type.startsWith('image/')) throw new Error('WALLPAPER_FILE_NOT_IMAGE')

  const image = await readImageFile(file)
  const sourceWidth = image.naturalWidth || image.width
  const sourceHeight = image.naturalHeight || image.height
  if (!sourceWidth || !sourceHeight) throw new Error('WALLPAPER_IMAGE_EMPTY')

  const ratio = readTargetRatio(options.ratio)
  const sourceRatio = sourceWidth / sourceHeight
  let cropWidth = sourceWidth
  let cropHeight = sourceHeight
  let cropX = 0
  let cropY = 0

  if (sourceRatio > ratio) {
    cropWidth = Math.round(sourceHeight * ratio)
    cropX = Math.round((sourceWidth - cropWidth) / 2)
  } else if (sourceRatio < ratio) {
    cropHeight = Math.round(sourceWidth / ratio)
    cropY = Math.round((sourceHeight - cropHeight) / 2)
  }

  const maxSize = Math.max(256, options.maxSize || DEFAULT_MAX_SIZE)
  const scale = Math.min(1, maxSize / Math.max(cropWidth, cropHeight))
  const width = Math.max(1, Math.round(cropWidth * scale))
  const height = Math.max(1, Math.round(cropHeight * scale))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('WALLPAPER_CANVAS_UNAVAILABLE')

  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(image, cropX, cropY, cropWidth, cropHeight, 0, 0, width, height)

  return {
    dataUrl: canvas.toDataURL('image/jpeg', options.quality || DEFAULT_QUALITY),
    width,
    height,
  }
}
