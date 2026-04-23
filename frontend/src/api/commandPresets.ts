import request from './client'

export interface CommandPreset {
  id: number
  command: string
  created_at: string
}

export interface CommandPresetCreate {
  command: string
}

const commandPresetsApi = {
  list: () =>
    request<CommandPreset[]>('/command-presets'),

  create: (data: CommandPresetCreate) =>
    request<CommandPreset>('/command-presets', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  delete: (id: number) =>
    request(`/command-presets/${id}`, {
      method: 'DELETE'
    })
}

export default commandPresetsApi
