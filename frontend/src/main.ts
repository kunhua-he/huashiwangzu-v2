import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './app-entry/router'
import { vPermission } from './platform/directives/v-permission'
import './styles/theme.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/common-components.css'
import './styles/notice-panel.css'
import './styles/desktop-shell.css'
import './styles/login-page.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.directive('permission', vPermission)

router.isReady().then(() => {
  app.mount('#app')
})
