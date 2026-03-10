import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LoginForm } from '@/components/Auth/LoginForm';

const mockPush = jest.fn();
const mockRefresh = jest.fn();
const mockSignIn = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
}));

jest.mock('next-auth/react', () => ({
  signIn: (...args: unknown[]) => mockSignIn(...args),
}));

describe('LoginForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSignIn.mockResolvedValue({ ok: true, error: null });
  });

  it('renders email and password inputs', () => {
    render(<LoginForm />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('renders a link to the register page', () => {
    render(<LoginForm />);

    const link = screen.getByRole('link', { name: /register/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/register');
  });

  it('shows error when email is empty', async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Email is required');
    });

    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it('shows error for invalid email format', async () => {
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'not-an-email' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Please enter a valid email address'
      );
    });

    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it('shows error when password is empty', async () => {
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Password is required'
      );
    });

    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it('calls signIn with credentials on valid submit', async () => {
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith('credentials', {
        email: 'test@example.com',
        password: 'password123',
        redirect: false,
      });
    });
  });

  it('redirects to dashboard on successful login', async () => {
    mockSignIn.mockResolvedValue({ ok: true, error: null });

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('shows error on failed login', async () => {
    mockSignIn.mockResolvedValue({
      ok: false,
      error: 'CredentialsSignin',
    });

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrongpassword' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Invalid email or password'
      );
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  it('shows loading state during submission', async () => {
    // Make signIn hang so we can observe loading state
    let resolveSignIn: (value: unknown) => void;
    mockSignIn.mockReturnValue(
      new Promise((resolve) => {
        resolveSignIn = resolve;
      })
    );

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/signing in/i)).toBeInTheDocument();
    });

    // Resolve to clean up
    resolveSignIn!({ ok: true, error: null });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });
  });

  it('disables inputs during submission', async () => {
    let resolveSignIn: (value: unknown) => void;
    mockSignIn.mockReturnValue(
      new Promise((resolve) => {
        resolveSignIn = resolve;
      })
    );

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeDisabled();
      expect(screen.getByLabelText(/password/i)).toBeDisabled();
    });

    resolveSignIn!({ ok: true, error: null });
  });
});
