import { validateLicense, activateLicense, getMyLicense } from '../../services/api';

const res = await validateLicense('LICENSE-KEY-123');
