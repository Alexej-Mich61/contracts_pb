# apps/contract_core/views.py
# from apps.audit.utils import add_event
# from apps.identity.models import Employee
# from apps.identity.permissions import ContractPermission
#
# class ContractCreateView(CreateView):
#     ...
#     def form_valid(self, form):
#         contract = form.save()
#         msg = add_event(contract, self.request.user, Event.EVENT_CREATED)
#         logger.info(msg)                      # в файл
#         send_chat_notification(contract, msg) # пример отправки в чат
#         return super().form_valid(form)
#
#
# class ContractUpdateView(UpdateView):
#     ...
#     def form_valid(self, form):
#         old_status = self.get_object().status
#         contract = form.save()
#         new_status = contract.status
#
#         if old_status != new_status:
#             msg = add_event(
#                 contract,
#                 self.request.user,
#                 Event.EVENT_STATUS_CHANGED,
#                 old_value=old_status,
#                 new_value=new_status,
#             )
#             send_chat_notification(contract, msg)
#
#         if "date_end" in form.changed_data:
#             msg = add_event(
#                 contract,
#                 self.request.user,
#                 Event.EVENT_DATE_CHANGED,
#                 old_value=form.initial["date_end"],
#                 new_value=contract.date_end,
#             )
#             send_chat_notification(contract, msg)
#
#         return super().form_valid(form)



