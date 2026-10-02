import type { ApiError } from "../../api/errors";
import styles from "./ErrorState.module.css";

interface ErrorStateProps {
  error: ApiError | Error | string;
  onRetry?: () => void;
  title?: string;
}

/** Renders a failed request honestly, with a retry action when the error class allows it. */
export function ErrorState({ error, onRetry, title = "Something went wrong" }: ErrorStateProps) {
  const message = typeof error === "string" ? error : error.message;
  const isApiError = typeof error === "object" && "isRetryable" in error;
  const retryable = isApiError ? (error as ApiError).isRetryable : true;
  const unauthorized = isApiError && (error as ApiError).isUnauthorized;
  const forbidden = isApiError && (error as ApiError).isForbidden;

  return (
    <div className={styles.wrapper} role="alert">
      <p className={styles.title}>
        {unauthorized ? "Authentication required" : forbidden ? "Access denied" : title}
      </p>
      <p className={styles.message}>{message}</p>
      {isApiError && (error as ApiError).requestId ? (
        <p className={styles.meta}>Request ID: {(error as ApiError).requestId}</p>
      ) : null}
      {onRetry && retryable ? (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
