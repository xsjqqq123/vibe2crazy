import request from './client'

export interface TunnelStatus {
  status: string
  remote_url: string | null
  token: string | null
  last_error: string | null
  server_url: string | null
}

export interface TunnelConfig {
  token: string
  use_tls?: boolean
  verify_tls?: boolean
}

export interface TunnelResponse {
  success: boolean
  message: string
}

const tunnelApi = {
  getStatus: () => request<TunnelStatus>('/tunnel/status'),

  saveConfig: (data: TunnelConfig) =>
    request<TunnelResponse>('/tunnel/config', {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  start: () =>
    request<TunnelResponse>('/tunnel/start', {
      method: 'POST'
    }),

  stop: () =>
    request<TunnelResponse>('/tunnel/stop', {
      method: 'POST'
    }),

  restart: () =>
    request<TunnelResponse>('/tunnel/restart', {
      method: 'POST'
    })
}

export default tunnelApi