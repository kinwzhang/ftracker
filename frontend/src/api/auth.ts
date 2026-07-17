import client from './client';

export async function fetchMe() {
  const { data } = await client.get('/auth/me/');
  return data;
}

export async function loginUser(username: string, password: string) {
  const { data } = await client.post('/auth/login/', { username, password });
  return data;
}

export async function logoutUser() {
  const { data } = await client.post('/auth/logout/');
  return data;
}
