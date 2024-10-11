"""create_user_click_table

Revision ID: 10e736db18fa
Revises: f73a15052ef2
Create Date: 2024-10-11 14:53:56.929270

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10e736db18fa'
down_revision = 'f73a15052ef2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_click',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('product_index', sa.Integer(), nullable=True),
    sa.Column('clicked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_click', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_click_user_id'), ['user_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_click', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_click_user_id'))

    op.drop_table('user_click')
    # ### end Alembic commands ###
