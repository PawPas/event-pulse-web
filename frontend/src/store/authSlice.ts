import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";
import { safeJsonParse } from "../utils/safeJsonParse";

interface AuthUser {
  id: string;
  email: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
}

// Sync-only init: localStorage reads are synchronous so ProtectedRoute never
// sees a transient null token on first render. If async rehydration (token
// refresh, remote session check) is ever added, introduce isInitialising: true
// here and guard ProtectedRoute with a spinner until it flips to false.
const initialState: AuthState = {
  token: localStorage.getItem("token"),
  user: safeJsonParse<AuthUser | null>(localStorage.getItem("user"), null),
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    loginSuccess(state, action: PayloadAction<{ token: string; user: AuthUser }>) {
      state.token = action.payload.token;
      state.user = action.payload.user;
      localStorage.setItem("token", action.payload.token);
      localStorage.setItem("user", JSON.stringify(action.payload.user));
    },
    logout(state) {
      state.token = null;
      state.user = null;
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    },
  },
});

export const { loginSuccess, logout } = authSlice.actions;
export default authSlice.reducer;
