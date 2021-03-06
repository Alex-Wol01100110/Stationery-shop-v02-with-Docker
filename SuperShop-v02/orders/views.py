from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse

from loguru import logger

from .models import OrderItem, Order
from .forms import OrderCreateForm
from .services import _check_order_payer, _check_cart_length_greater_than_zero
from cart.cart import Cart

import weasyprint


@logger.catch
def order_create(request):
    cart = Cart(request)
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if cart.coupon:
                order.coupon = cart.coupon
                order.discount = cart.coupon.discount
            order.save()
            for item in cart:
                OrderItem.objects.create(order=order,
                                        product=item['product'],
                                        price=item['price'],
                                        quantity=item['quantity'])
            # clear the cart
            cart.clear()
            # set the order in the sessin
            request.session['order_id'] = order.id
            # Redirect for payment.
            return redirect(reverse('payment:process'))
    else:
        _check_cart_length_greater_than_zero(cart)
        form = OrderCreateForm()
    return render(request,
                  'orders/order/create.html',
                  {'cart': cart, 'form': form})

@logger.catch
@staff_member_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request,
                  'admin/orders/order/detail.html',
                  {'order': order})

@logger.catch
@staff_member_required
def admin_order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    html = render_to_string('orders/order/pdf.html',
                            {'order': order})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename=order_{order.id}.pdf'
    weasyprint.HTML(string=html).write_pdf(response,
        stylesheets=[weasyprint.CSS(
            settings.STATIC_ROOT + 'css/pdf.css')])
    return response

@logger.catch
@login_required
def order_list(request):
    user_orders = Order.objects.filter(payer=request.user).order_by('created')
    return render(request,
                  'user/orders/order/order_list.html',
                  {'user_orders': user_orders})

@logger.catch
@login_required
def order_detail(request, order_id):
    """Show a single topic and all its entries."""
    order = get_object_or_404(Order, id=order_id)
    order_payer = _check_order_payer(order.payer, request)
    if order_payer == False:
        return redirect('orders:order_list')
    else:
        return render(request,
                      'user/orders/order/order_detail.html',
                      {'order': order})
