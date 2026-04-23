import request from './client'

export interface LoginResponse {
  token: string
}

export interface SessionResponse {
  authenticated: boolean
  expires_at?: string
}

export interface PasswordStatusResponse {
  is_set: boolean
}

export interface ChangePasswordResponse {
  success: boolean
  message: string
}

const authApi = {
  login: (password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password })
    }),

  logout: () =>
    request('/auth/logout', {
      method: 'DELETE'
    }),

  getMe: () =>
    request<SessionResponse>('/auth/me'),

  getPasswordStatus: () =>
    request<PasswordStatusResponse>('/auth/password-status'),

  changePassword: (newPassword: string, oldPassword?: string) =>
    request<ChangePasswordResponse>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        new_password: newPassword,
        old_password: oldPassword || undefined
      })
    })
}

export default authApi
