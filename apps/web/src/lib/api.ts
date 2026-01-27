const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080"

// Debug: Log API URL to console
console.log('[API Client] VITE_API_URL:', import.meta.env.VITE_API_URL)
console.log('[API Client] API_URL:', API_URL)
console.log('[API Client] All env vars:', import.meta.env)

export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data: T
  code: string
}

export interface LoginRequest {
  identifier: string
  password: string
}

export interface AuthData {
  user: {
    id: string
    username: string
    email: string
    full_name?: string
    avatar_url?: string
  }
  access_token: string
  refresh_token: string
}

export interface LogoutRequest {
  access_token: string
  refresh_token: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface SendEmailVerificationRequest {
  email: string
}

export interface VerifyEmailCodeRequest {
  email: string
  otp: string
}

export interface CompleteRegistrationRequest {
  verification_token: string
  username: string
  password: string
}

export interface ResendOTPRequest {
  email: string
}

export interface VerificationTokenResponse {
  verification_token: string
}

// User Types
export interface ImageData {
  url: string
  public_id: string
}

export interface UserSettings {
  language: "vi" | "en"
  theme: "light" | "dark"
  notify_new_features: boolean
}

export interface User {
  id: string
  username: string
  email: string
  role: "user" | "admin"
  provider: "local" | "google"
  is_verified: boolean
  is_active: boolean
  avatar?: ImageData
  settings: UserSettings
  created_at: string
}

export interface UpdateProfileRequest {
  username?: string
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

export interface UpdateSettingsRequest {
  language?: "vi" | "en"
  theme?: "light" | "dark"
  notify_new_features?: boolean
}

// Chat Types
export interface ChatRequest {
  message: string
  session_id?: string // Optional, creates new session if not provided
}

// Source Types (Reasoning-based RAG)
export interface NodeInfo {
  node_id: string
  title: string
  text: string
}

export interface SourceInfo {
  doc_id: string
  doc_title: string
  doc_type: "regulation" | "curriculum"
  year: number
  source_url?: string | null // URL for curriculum
  pdf_url?: string | null    // PDF download URL for regulation
  nodes: NodeInfo[]
}

export interface ChatMessageMetadata {
  sources?: SourceInfo[]
  tokens_used?: number
  latency_ms?: number
  agent_latency_ms?: number
}

export interface ChatMessageResponse {
  id: string
  role: "user" | "assistant"
  content: string
  metadata?: ChatMessageMetadata
  created_at: string
}

export interface ChatResponse {
  session_id: string
  message: ChatMessageResponse // The assistant's response
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface UpdateSessionTitleRequest {
  title: string
}

export interface GetSessionsQuery {
  page?: number
  page_size?: number
}

class ApiClient {
  private baseURL: string
  private isRefreshing = false
  private refreshSubscribers: Array<(token: string) => void> = []

  constructor() {
    this.baseURL = API_URL
  }

  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem("accessToken")
    if (token) {
      return {
        Authorization: `Bearer ${token}`,
      }
    }
    return {}
  }

  private onRefreshed(token: string) {
    this.refreshSubscribers.forEach((callback) => callback(token))
    this.refreshSubscribers = []
  }

  private addRefreshSubscriber(callback: (token: string) => void) {
    this.refreshSubscribers.push(callback)
  }

  private async handleTokenRefresh(): Promise<string> {
    const refreshToken = localStorage.getItem("refreshToken")
    if (!refreshToken) {
      throw new Error("No refresh token available")
    }

    try {
      const response = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: 'include', // Nhận cookies mới sau khi refresh
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!response.ok) {
        throw new Error("Failed to refresh token")
      }

      const data = await response.json()
      if (data.success && data.data) {
        localStorage.setItem("accessToken", data.data.access_token)
        localStorage.setItem("refreshToken", data.data.refresh_token)
        return data.data.access_token
      }

      throw new Error("Invalid refresh response")
    } catch (error) {
      // Refresh failed, clear tokens and redirect to login
      localStorage.removeItem("user")
      localStorage.removeItem("accessToken")
      localStorage.removeItem("refreshToken")
      window.location.href = "/login"
      throw error
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retry = true
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseURL}${endpoint}`

    const defaultHeaders: HeadersInit = {
      "Content-Type": "application/json",
      ...this.getAuthHeaders(),
    }

    const config: RequestInit = {
      ...options,
      credentials: 'include', // Cho phép browser nhận và gửi cookies
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    }

    try {
      const response = await fetch(url, config)

      // Check if response is JSON
      const contentType = response.headers.get("content-type")
      if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Server không trả về JSON. Có thể backend chưa chạy hoặc URL không đúng.")
      }

      const data = await response.json()

      // Handle 401 Unauthorized - Token expired
      if (response.status === 401 && retry && !endpoint.includes("/auth/refresh")) {
        if (!this.isRefreshing) {
          this.isRefreshing = true
          try {
            const newToken = await this.handleTokenRefresh()
            this.isRefreshing = false
            this.onRefreshed(newToken)
            // Retry the original request with new token
            return this.request<T>(endpoint, options, false)
          } catch (refreshError) {
            this.isRefreshing = false
            throw refreshError
          }
        } else {
          // Wait for the ongoing refresh to complete
          return new Promise((resolve, reject) => {
            this.addRefreshSubscriber((token: string) => {
              // Retry with new token
              this.request<T>(endpoint, options, false)
                .then(resolve)
                .catch(reject)
            })
          })
        }
      }

      if (!response.ok) {
        throw new Error(data.message || "Request failed")
      }

      return data
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error("Lỗi parse JSON từ server. Vui lòng kiểm tra backend.")
      }
      throw error
    }
  }

  // Authentication
  async login(credentials: LoginRequest): Promise<ApiResponse<AuthData>> {
    return this.request<AuthData>("/api/v1/auth/local/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    })
  }

  async logout(tokens: LogoutRequest): Promise<ApiResponse> {
    return this.request("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify(tokens),
    })
  }

  async refreshToken(refreshToken: string): Promise<ApiResponse<{ access_token: string; refresh_token: string }>> {
    return this.request("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  }

  // Registration Flow
  async sendEmailVerification(email: string): Promise<ApiResponse> {
    return this.request("/api/v1/auth/local/send-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    })
  }

  async verifyEmailCode(email: string, otp: string): Promise<ApiResponse<VerificationTokenResponse>> {
    return this.request<VerificationTokenResponse>("/api/v1/auth/local/verify-email", {
      method: "POST",
      body: JSON.stringify({ email, otp }),
    })
  }

  async completeRegistration(
    verificationToken: string,
    username: string,
    password: string
  ): Promise<ApiResponse<AuthData>> {
    return this.request<AuthData>("/api/v1/auth/local/complete-registration", {
      method: "POST",
      body: JSON.stringify({
        verification_token: verificationToken,
        username,
        password,
      }),
    })
  }

  async resendOTP(email: string): Promise<ApiResponse> {
    return this.request("/api/v1/auth/local/resend-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    })
  }

  // User Profile
  async getUserProfile(): Promise<ApiResponse<User>> {
    return this.request<User>("/api/v1/users/me", {
      method: "GET",
    })
  }

  async updateUserProfile(data: UpdateProfileRequest): Promise<ApiResponse<User>> {
    return this.request<User>("/api/v1/users/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  async changePassword(data: ChangePasswordRequest): Promise<ApiResponse> {
    return this.request("/api/v1/users/me/password", {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  // Avatar Management
  async uploadAvatar(file: File): Promise<ApiResponse<ImageData>> {
    const formData = new FormData()
    formData.append("avatar", file)

    const url = `${this.baseURL}/api/v1/users/me/avatar`
    const token = localStorage.getItem("accessToken")
    const headers: HeadersInit = {}
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    // Don't set Content-Type - browser will set it with boundary

    try {
      const response = await fetch(url, {
        method: "POST",
        headers,
        credentials: 'include', // Gửi cookies khi upload avatar
        body: formData,
      })

      const contentType = response.headers.get("content-type")
      if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Server không trả về JSON")
      }

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.message || "Upload failed")
      }

      return data
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error("Lỗi parse JSON từ server")
      }
      throw error
    }
  }

  async deleteAvatar(): Promise<ApiResponse> {
    return this.request("/api/v1/users/me/avatar", {
      method: "DELETE",
    })
  }

  // User Settings
  async getSettings(): Promise<ApiResponse<UserSettings>> {
    return this.request<UserSettings>("/api/v1/users/me/settings", {
      method: "GET",
    })
  }

  async updateSettings(data: UpdateSettingsRequest): Promise<ApiResponse<UserSettings>> {
    return this.request<UserSettings>("/api/v1/users/me/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  // Chat APIs
  async sendChatMessage(data: ChatRequest): Promise<ApiResponse<ChatResponse>> {
    return this.request<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async getChatSessions(query?: GetSessionsQuery): Promise<ApiResponse<ChatSession[]>> {
    const params = new URLSearchParams()
    if (query?.page) params.append("page", query.page.toString())
    if (query?.page_size) params.append("page_size", query.page_size.toString())

    const queryString = params.toString()
    const endpoint = queryString ? `/api/v1/chat/sessions?${queryString}` : "/api/v1/chat/sessions"

    return this.request<ChatSession[]>(endpoint, {
      method: "GET",
    })
  }

  async getChatSession(sessionId: string): Promise<ApiResponse<ChatSession>> {
    return this.request<ChatSession>(`/api/v1/chat/sessions/${sessionId}`, {
      method: "GET",
    })
  }

  async getChatMessages(sessionId: string, limit?: number): Promise<ApiResponse<ChatMessageResponse[]>> {
    const params = new URLSearchParams()
    if (limit) params.append("limit", limit.toString())

    const queryString = params.toString()
    const endpoint = queryString
      ? `/api/v1/chat/sessions/${sessionId}/messages?${queryString}`
      : `/api/v1/chat/sessions/${sessionId}/messages`

    return this.request<ChatMessageResponse[]>(endpoint, {
      method: "GET",
    })
  }

  async deleteChatSession(sessionId: string): Promise<ApiResponse> {
    return this.request(`/api/v1/chat/sessions/${sessionId}`, {
      method: "DELETE",
    })
  }

  async updateSessionTitle(sessionId: string, data: UpdateSessionTitleRequest): Promise<ApiResponse<ChatSession>> {
    return this.request<ChatSession>(`/api/v1/chat/sessions/${sessionId}/title`, {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }
}

export const apiClient = new ApiClient()
