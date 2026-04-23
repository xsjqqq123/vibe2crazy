import { createApp, h, ref, nextTick } from 'vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

export interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

let appInstance: ReturnType<typeof createApp> | null = null
let mountPoint: HTMLElement | null = null

export function useConfirm() {
  const showConfirm = (options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      // Clean up any previous instance
      if (appInstance && mountPoint) {
        appInstance.unmount()
        appInstance = null
        if (mountPoint.parentNode) {
          mountPoint.parentNode.removeChild(mountPoint)
        }
        mountPoint = null
      }

      // Create a wrapper div for mounting
      const newMountPoint = document.createElement('div')
      mountPoint = newMountPoint
      document.body.appendChild(mountPoint)

      // Create the app instance
      appInstance = createApp({
        setup() {
          const show = ref(true)

          const handleConfirm = () => {
            show.value = false
            // Unmount after transition
            nextTick(() => {
              if (appInstance && mountPoint) {
                appInstance.unmount()
                appInstance = null
                if (mountPoint.parentNode) {
                  mountPoint.parentNode.removeChild(mountPoint)
                }
                mountPoint = null
              }
              resolve(true)
            })
          }

          const handleCancel = () => {
            show.value = false
            // Unmount after transition
            nextTick(() => {
              if (appInstance && mountPoint) {
                appInstance.unmount()
                appInstance = null
                if (mountPoint.parentNode) {
                  mountPoint.parentNode.removeChild(mountPoint)
                }
                mountPoint = null
              }
              resolve(false)
            })
          }

          return () =>
            h(ConfirmDialog, {
              show: show.value,
              title: options.title,
              message: options.message,
              confirmText: options.confirmText,
              cancelText: options.cancelText,
              danger: options.danger ?? false,
              onConfirm: handleConfirm,
              onCancel: handleCancel
            })
        }
      })

      appInstance.mount(mountPoint)
    })
  }

  return { showConfirm }
}