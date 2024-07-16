import contextlib
from typing import List, Tuple, Generator

import pywintypes
import win32api
import win32con
import win32security

from windows_downdate.process_utils import get_process_id_by_name


@contextlib.contextmanager
def smart_open_handle(open_func, *args, **kwargs) -> Generator[pywintypes.HANDLEType, None, None]:
    handle = open_func(*args, **kwargs)
    try:
        yield handle
    finally:
        handle.close()


@contextlib.contextmanager
def smart_open_process(*args, **kwargs) -> Generator[pywintypes.HANDLEType, None, None]:
    with smart_open_handle(win32api.OpenProcess, *args, **kwargs) as process_handle:
        yield process_handle


@contextlib.contextmanager
def smart_open_process_token(*args, **kwargs) -> Generator[pywintypes.HANDLEType, None, None]:
    with smart_open_handle(win32security.OpenProcessToken, *args, **kwargs) as process_token_handle:
        yield process_token_handle


@contextlib.contextmanager
def smart_duplicate_token_ex(*args, **kwargs) -> Generator[pywintypes.HANDLEType, None, None]:
    with smart_open_handle(win32security.DuplicateTokenEx, *args, **kwargs) as dup_process_token_handle:
        yield dup_process_token_handle


@contextlib.contextmanager
def smart_process_impersonator(process_name: str) -> Generator[None, None, None]:
    process_id = get_process_id_by_name(process_name)
    with smart_open_process(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id) as process_handle:
        with smart_open_process_token(process_handle, win32con.TOKEN_DUPLICATE) as process_token_handle:
            with smart_duplicate_token_ex(process_token_handle,
                                          win32security.SecurityImpersonation,
                                          win32con.TOKEN_ALL_ACCESS,
                                          win32security.TokenImpersonation,
                                          win32security.SECURITY_ATTRIBUTES()) as dup_process_token_handle:
                win32security.ImpersonateLoggedOnUser(dup_process_token_handle)
    try:
        yield
    finally:
        win32security.RevertToSelf()


def convert_privilege_name_to_luid(privilege: Tuple[str, int]) -> Tuple[int, int]:
    privilege_name, privilege_attrs = privilege
    luid = win32security.LookupPrivilegeValue(None, privilege_name)

    return luid, privilege_attrs


def adjust_token_privileges(privileges: List[Tuple[str, int]], disable_all_privileges_flag: bool = False) -> None:
    privileges_with_luids = [convert_privilege_name_to_luid(privilege) for privilege in privileges]
    token_handle = win32security.OpenProcessToken(win32api.GetCurrentProcess(),
                                                  win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY)
    win32security.AdjustTokenPrivileges(token_handle, disable_all_privileges_flag, privileges_with_luids)


def enable_privilege(privilege_name: str) -> None:
    privilege = [(privilege_name, win32security.SE_PRIVILEGE_ENABLED)]
    adjust_token_privileges(privilege)


def is_administrator() -> bool:
    administrator_sid = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)
    return win32security.CheckTokenMembership(None, administrator_sid)
