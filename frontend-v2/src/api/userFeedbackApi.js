// User feedback: the "Send feedback" form in the profile menu. Not to be
// confused with `feedbackApi`, which is the meal-plan accept/reject signal.
//
// The error-copy helpers are not defined here: they live in `catalogApi` and
// the modal imports them from there, so its errors read like every other
// screen's.
import { request } from './client';

const OPTIONAL = ['page_path', 'user_agent', 'viewport_width'];

export const userFeedbackApi = {
  // Multipart because of the optional screenshot; `request()` sees the
  // FormData and leaves the content type to the browser. Resolves to
  // `{ ref_code }`.
  submit: (fields, file) => {
    const body = new FormData();
    body.append('title', fields.title);
    body.append('body', fields.body);
    body.append('type', fields.type);
    OPTIONAL.forEach((key) => {
      if (fields[key] !== undefined) body.append(key, fields[key]);
    });
    if (file) body.append('screenshot', file);
    return request('/feedback', { method: 'POST', body });
  },
};

export default userFeedbackApi;
